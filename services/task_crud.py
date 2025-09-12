"""CRUD-операции для работы с задачами."""

import logging

from peewee import JOIN, fn
from playhouse.shortcuts import prefetch

from utils.time_utils import now_str
from database.db import db
from database.models import (
    Client,
    Deal,
    Policy,
    Task,
    DealExecutor,
    Executor,
)
from .task_states import IDLE, QUEUED


logger = logging.getLogger(__name__)


# Поля, допустимые для создания и обновления задач
TASK_ALLOWED_FIELDS = {
    "title",
    "due_date",
    "deal_id",
    "policy_id",
    "is_done",
    "note",
    "dispatch_state",
    "queued_at",
    "tg_chat_id",
    "tg_message_id",
}


def _clean_task_data(data: dict[str, object]) -> dict[str, object]:
    """Отфильтровать допустимые поля и убрать пустые значения."""
    clean: dict[str, object] = {}
    for key, value in data.items():
        if value in ("", None):
            continue
        if key in TASK_ALLOWED_FIELDS:
            clean[key] = value
        elif key == "deal" and hasattr(value, "id"):
            clean["deal_id"] = value.id
        elif key == "policy" and hasattr(value, "id"):
            clean["policy_id"] = value.id
    return clean


def get_all_tasks():
    """Вернуть все задачи без удалённых."""
    return Task.active()


def get_pending_tasks():
    """Невыполненные активные задачи."""
    return Task.active().where(Task.is_done == False)


def get_task_counts_by_deal_id(deal_id: int) -> tuple[int, int]:
    """Подсчитать количество открытых и закрытых задач по сделке."""
    base = Task.active().where(Task.deal_id == deal_id)
    open_count = base.where(Task.is_done == False).count()
    closed_count = base.where(Task.is_done == True).count()
    return open_count, closed_count


def add_task(**kwargs):
    """Создать задачу."""
    clean_data = _clean_task_data(kwargs)

    try:
        with db.atomic():
            task = Task.create(**clean_data)
    except Exception as e:  # pragma: no cover - logging
        logger.error("❌ Ошибка при создании задачи: %s", e)
        raise

    logger.info(
        "📝 Создана задача #%s: '%s' (due %s)", task.id, task.title, task.due_date
    )
    try:
        from services.telegram_service import notify_admin

        notify_admin(f"🆕 Создана задача #{task.id}: {task.title}")
    except Exception:  # pragma: no cover - logging
        logger.debug("Failed to notify admin about new task", exc_info=True)
    return task


def update_task(task: Task, **fields) -> Task:
    """Изменить поля задачи."""

    is_marking_done = fields.get("is_done") is True
    raw_note = fields.get("note")
    user_text = (
        raw_note.strip()
        if isinstance(raw_note, str) and raw_note.strip()
        else "Задача выполнена."
    )

    clean_fields = _clean_task_data(fields)

    with db.atomic():
        for key, value in clean_fields.items():
            setattr(task, key, value)

        if is_marking_done:
            task.dispatch_state = IDLE
            task.tg_chat_id = None
            task.tg_message_id = None

        task.save()

        if is_marking_done:
            timestamp = now_str()
            header = f"[{timestamp}] — Задача №{task.id}: {task.title}"
            body_lines = user_text.splitlines()
            body = "\n".join(body_lines)
            entry = f"{header}\n{body}\n"

            if task.deal_id:
                deal = Deal.get_or_none(Deal.id == task.deal_id)
                if deal:
                    existing = deal.calculations or ""
                    deal.calculations = entry + existing
                    deal.save()

            if task.policy_id:
                policy = Policy.get_or_none(Policy.id == task.policy_id)
                if policy:
                    existing = policy.note or ""
                    policy.note = entry + existing
                    policy.save()

    logger.info("✏️ Обновлена задача #%s", task.id)
    return task


def mark_task_deleted(task: Task | int):
    task_obj = task if isinstance(task, Task) else Task.get_or_none(Task.id == task)
    if task_obj:
        with db.atomic():
            task_obj.soft_delete()
        logger.info("🗑 Задача #%s помечена как удалённая", task_obj.id)
    else:
        logger.warning("❗ Задача %s не найдена для удаления", task)


def build_task_query(
    include_done: bool = True,
    include_deleted: bool = False,
    search_text: str | None = None,
    only_queued: bool = False,
    due_before=None,
    deal_id: int | None = None,
    policy_id: int | None = None,
    sort_field: str = "due_date",
    sort_order: str = "asc",
    column_filters: dict[str, str] | None = None,
):
    query = Task.active() if not include_deleted else Task.select()
    if not include_done:
        query = query.where(Task.is_done == False)
    if only_queued:
        query = query.where(Task.dispatch_state == QUEUED)
    if search_text:
        query = (
            query.join(Deal, JOIN.LEFT_OUTER)
            .join(Client, JOIN.LEFT_OUTER, on=(Deal.client == Client.id))
            .switch(Task)
            .join(Policy, JOIN.LEFT_OUTER)
            .where(
                (Task.title.contains(search_text))
                | (Task.note.contains(search_text))
                | (Deal.description.contains(search_text))
                | (Policy.policy_number.contains(search_text))
                | (Client.name.contains(search_text))
            )
        )
    if due_before:
        query = query.where(Task.due_date <= due_before)
    if deal_id:
        query = query.where(Task.deal == deal_id)
    if policy_id:
        query = query.where(Task.policy == policy_id)

    from services.query_utils import apply_column_filters, apply_field_filters

    field_filters: dict = {}
    name_filters: dict[str, str] = {}
    if column_filters:
        for key, val in column_filters.items():
            if key == "full_name":
                field_filters[Executor.full_name] = val
            else:
                name_filters[key] = val

    query = apply_column_filters(query, name_filters, Task)

    join_executor = bool(field_filters) or sort_field == "executor"
    if join_executor:
        policy_alias = Policy.alias()
        deal_alias = Deal.alias()
        query = (
            query.switch(Task)
            .join(policy_alias, JOIN.LEFT_OUTER)
            .switch(Task)
            .join(
                deal_alias,
                JOIN.LEFT_OUTER,
                on=(deal_alias.id == fn.COALESCE(Task.deal, policy_alias.deal)),
            )
            .join(DealExecutor, JOIN.LEFT_OUTER, on=(DealExecutor.deal == deal_alias.id))
            .join(Executor, JOIN.LEFT_OUTER, on=(DealExecutor.executor == Executor.id))
        )
        if field_filters:
            query = apply_field_filters(query, field_filters)

    return query


def get_tasks_page(
    page: int,
    per_page: int,
    sort_field="due_date",
    sort_order="asc",
    column_filters: dict[str, str] | None = None,
    **filters,
):
    """Получить страницу задач."""
    logger.debug("🔽 Применяем сортировку: field=%s, order=%s", sort_field, sort_order)
    offset = (page - 1) * per_page
    query = build_task_query(
        column_filters=column_filters, sort_field=sort_field, **filters
    )
    if sort_field == "executor":
        order = (
            Executor.full_name.asc()
            if sort_order == "asc"
            else Executor.full_name.desc()
        )
        query = query.distinct().order_by(order, Task.id.asc())
    elif sort_field and hasattr(Task, sort_field):
        field = getattr(Task, sort_field)
        order = field.asc() if sort_order == "asc" else field.desc()
        query = query.order_by(order, Task.id.asc())
    else:
        query = query.order_by(Task.due_date.desc(), Task.id.desc())
    return query.offset(offset).limit(per_page)


def get_pending_tasks_page(page: int, per_page: int):
    """Получить страницу невыполненных задач."""
    offset = (page - 1) * per_page
    return (
        Task.active()
        .where(Task.is_done == False)
        .offset(offset)
        .limit(per_page)
    )


def get_tasks_by_deal(deal_id: int) -> list[Task]:
    """Получить задачи, связанные со сделкой."""
    policy_subq = (
        Policy.select(Policy.id)
        .where(Policy.deal_id == deal_id)
    )
    return Task.active().where(
        (Task.deal_id == deal_id) | (Task.policy_id.in_(policy_subq))
    )


def get_incomplete_tasks_by_deal(deal_id: int) -> list[Task]:
    """Получить невыполненные задачи сделки с предзагрузкой связей."""
    policy_subq = (
        Policy.select(Policy.id)
        .where(Policy.deal_id == deal_id)
    )
    base = (
        Task.active()
        .where(
            (
                (Task.deal_id == deal_id)
                | (Task.policy_id.in_(policy_subq))
            )
            & (Task.is_done == False)
        )
    )
    return list(prefetch(base, Deal, Policy, Client))


def get_incomplete_tasks_for_executor(tg_id: int) -> list[Task]:
    """Вернуть невыполненные задачи по сделкам исполнителя."""
    from services import executor_service as es

    deals = es.get_deals_for_executor(tg_id)
    if not deals:
        return []
    deal_ids = [d.id for d in deals]
    policy_subq = (
        Policy.select(Policy.id)
        .where(Policy.deal_id.in_(deal_ids))
    )
    base = (
        Task.active()
        .where(
            (
                (Task.deal_id.in_(deal_ids))
                | (Task.policy_id.in_(policy_subq))
            )
            & (Task.is_done == False)
        )
    )
    return list(prefetch(base, Deal, Client, Policy))


def get_incomplete_task(task_id: int) -> Task | None:
    """Вернуть невыполненную задачу с предзагрузкой связей."""
    base = (
        Task.active()
        .where((Task.id == task_id) & (Task.is_done == False))
    )
    result = list(prefetch(base, Deal, Policy, Client))
    return result[0] if result else None


__all__ = [
    "get_all_tasks",
    "get_pending_tasks",
    "get_task_counts_by_deal_id",
    "add_task",
    "update_task",
    "mark_task_deleted",
    "build_task_query",
    "get_tasks_page",
    "get_pending_tasks_page",
    "get_tasks_by_deal",
    "get_incomplete_tasks_by_deal",
    "get_incomplete_tasks_for_executor",
    "get_incomplete_task",
]

