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

ALLOWED_SORT_FIELDS: dict[str, object] = {
    "due_date": Task.due_date,
    "title": Task.title,
    "id": Task.id,
    "queued_at": Task.queued_at,
    "is_done": Task.is_done,
    "dispatch_state": Task.dispatch_state,
    "deal": Task.deal,
    "policy": Task.policy,
}


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


def _filter_task_fields(data: dict[str, object]) -> dict[str, object]:
    """Отфильтровать входные данные, оставив только допустимые поля."""
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

    clean_data = _filter_task_fields(kwargs)


    try:
        with db.atomic():
            task = Task.create(**clean_data)
    except Exception as e:  # pragma: no cover - logging
        logger.error("❌ Ошибка при создании задачи: %s", e)
        raise

    logger.info(
        "📝 Создана задача id=%s: '%s' (due %s)", task.id, task.title, task.due_date
    )
    from services.telegram_service import notify_admin_safe

    notify_admin_safe(f"🆕 Создана задача #{task.id}: {task.title}")
    return task


def update_task(task: Task, **fields) -> Task:
    """Изменить поля задачи."""

    clean_fields = _filter_task_fields(fields)
    is_marking_done = clean_fields.get("is_done") is True

    raw_note = fields.get("note")
    user_text = (
        raw_note.strip()
        if isinstance(raw_note, str) and raw_note.strip()
        else "Задача выполнена."
    )

    log_updates: dict[str, dict[str, object]] = {}

    with db.atomic():
        for key, value in clean_fields.items():
            old_value = getattr(task, key)
            if old_value != value:
                log_updates[key] = {"old": old_value, "new": value}
            setattr(task, key, value)

        if is_marking_done:
            if task.dispatch_state != IDLE:
                log_updates["dispatch_state"] = {
                    "old": task.dispatch_state,
                    "new": IDLE,
                }
            if task.tg_chat_id is not None:
                log_updates["tg_chat_id"] = {
                    "old": task.tg_chat_id,
                    "new": None,
                }
            if task.tg_message_id is not None:
                log_updates["tg_message_id"] = {
                    "old": task.tg_message_id,
                    "new": None,
                }
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

    logger.info("✏️ Обновлена задача id=%s: %s", task.id, log_updates)
    return task


def mark_task_deleted(task: Task | int):
    task_obj = task if isinstance(task, Task) else Task.get_or_none(Task.id == task)
    if task_obj:
        with db.atomic():
            task_obj.soft_delete()
        logger.info("🗑 Задача id=%s помечена как удалённая", task_obj.id)
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
    sort_field = (
        sort_field
        if sort_field in ALLOWED_SORT_FIELDS or sort_field == "executor"
        else "due_date"
    )

    query = Task.active() if not include_deleted else Task.select()
    if not include_done:
        query = query.where(Task.is_done == False)
    if only_queued:
        query = query.where(Task.dispatch_state == QUEUED)
    if search_text:
        from services.query_utils import build_or_condition

        query = (
            query.join(Deal, JOIN.LEFT_OUTER)
            .join(Client, JOIN.LEFT_OUTER, on=(Deal.client == Client.id))
            .switch(Task)
            .join(Policy, JOIN.LEFT_OUTER)
        )
        condition = build_or_condition(
            [
                Task.title,
                Task.note,
                Deal.description,
                Policy.policy_number,
                Client.name,
            ],
            search_text,
        )
        if condition is not None:
            query = query.where(condition)
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

    if sort_field not in ALLOWED_SORT_FIELDS and sort_field != "executor":
        sort_field = "due_date"

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
    if sort_field not in ALLOWED_SORT_FIELDS and sort_field != "executor":
        sort_field = "due_date"

    logger.debug("🔽 Применяем сортировку: field=%s, order=%s", sort_field, sort_order)
    sort_field = (
        sort_field
        if sort_field in ALLOWED_SORT_FIELDS or sort_field == "executor"
        else "due_date"
    )
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
    else:
        field = ALLOWED_SORT_FIELDS.get(sort_field, Task.due_date)
        order = field.asc() if sort_order == "asc" else field.desc()
        query = query.order_by(order, Task.id.asc())
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

