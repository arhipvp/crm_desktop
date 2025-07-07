"""Сервисные функции для работы с задачами."""

import logging

logger = logging.getLogger(__name__)
import datetime as _dt
from utils.time_utils import now_str

from peewee import JOIN
from playhouse.shortcuts import prefetch

from database.db import db
from database.models import Client, Deal, Policy, Task
from services.deal_service import refresh_deal_drive_link
from services.deal_service import get_deal_by_id  # re-export


# ───────────────────────── базовые CRUD ─────────────────────────
def get_all_tasks():
    """Вернуть все задачи без удалённых."""
    return Task.select().where(Task.is_deleted == False)


def get_pending_tasks():
    """Невыполненные активные задачи."""
    return Task.select().where((Task.is_done == False) & (Task.is_deleted == False))


def add_task(**kwargs):
    """Создать задачу.

    Args:
        **kwargs: Поля задачи, такие как ``title`` и ``due_date``.

    Returns:
        Task: Созданная задача.
    """
    allowed_fields = {
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

    clean_data = {}

    for key, value in kwargs.items():
        if key in allowed_fields and value not in ("", None):
            clean_data[key] = value
        elif key == "deal" and hasattr(value, "id"):
            clean_data["deal_id"] = value.id
        elif key == "policy" and hasattr(value, "id"):
            clean_data["policy_id"] = value.id

    clean_data["is_deleted"] = False
    try:
        task = Task.create(**clean_data)
    except Exception as e:
        logger.error("❌ Ошибка при создании задачи: %s", e)
        raise

    logger.info(
        "📝 Создана задача #%s: '%s' (due %s)", task.id, task.title, task.due_date
    )

    try:
        from services.telegram_service import notify_admin
        notify_admin(f"🆕 Создана задача #{task.id}: {task.title}")
    except Exception:
        logger.debug("Failed to notify admin about new task", exc_info=True)

    return task


def update_task(task: Task, **fields) -> Task:
    """Изменить поля задачи.

    Args:
        task: Задача для изменения.
        **fields: Обновляемые поля.

    Returns:
        Task: Обновлённая задача.
    """
    allowed_fields = {
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

    # Определяем, снимают ли is_done
    is_marking_done = fields.get("is_done") is True
    raw_note = fields.get("note")
    user_text = (
        raw_note.strip()
        if isinstance(raw_note, str) and raw_note.strip()
        else "Задача выполнена."
    )

    # 1) Обновляем поля задачи
    for key, value in fields.items():
        if value in ("", None):
            continue
        if key == "deal" and hasattr(value, "id"):
            task.deal_id = value.id
        elif key == "policy" and hasattr(value, "id"):
            task.policy_id = value.id
        elif key in allowed_fields:
            setattr(task, key, value)

    if is_marking_done:
        task.dispatch_state = "idle"
        task.tg_chat_id = None
        task.tg_message_id = None

    task.save()
    logger.info("✅ Задача #%s помечена как выполненная", task.id)

    # 2) Если задача отмечена выполненной — формируем новую запись
    if is_marking_done:
        timestamp = now_str()
        header = f"[{timestamp}] — Задача №{task.id}: {task.title}"
        # Собираем тело, сохраняем оригинальные переносы
        body_lines = user_text.splitlines()
        body = "\n".join(body_lines)
        entry = f"{header}\n{body}\n"  # в конце перенос, чтобы было читаемо

        # 3) Препендим к сделке
        if task.deal_id:
            deal = Deal.get_or_none(Deal.id == task.deal_id)
            if deal:
                existing = deal.calculations or ""
                deal.calculations = entry + existing
                deal.save()

        # 4) Препендим к полису
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
        task_obj.is_deleted = True
        task_obj.save()
        logger.info("🗑 Задача #%s помечена как удалённая", task_obj.id)
    else:
        logger.warning("❗ Задача %s не найдена для удаления", task)


# ─────────────────────── очередь Telegram ───────────────────────
def queue_task(task_id: int):
    """Поставить задачу в очередь (idle → queued)."""
    t = Task.get_or_none(Task.id == task_id, Task.is_deleted == False)
    if t and t.dispatch_state == "idle":
        t.dispatch_state = "queued"
        t.queued_at = _dt.datetime.utcnow()
        t.save()
        logger.info("📤 Задача #%s поставлена в очередь", t.id)
        try:
            from services.telegram_service import notify_admin
            notify_admin(f"📤 Задача #{t.id} поставлена в очередь")
        except Exception:
            logger.debug("Failed to notify admin", exc_info=True)
    else:
        logger.info(
            "⏭ Задача #%s не поставлена в очередь: состояние %s", t.id, t.dispatch_state
        )


def get_clients_with_queued_tasks() -> list[Client]:
    """Вернуть уникальных клиентов с задачами в состоянии ``queued``."""
    base = Task.select().where(
        (Task.dispatch_state == "queued") & (Task.is_deleted == False)
    )
    tasks = prefetch(base, Deal, Policy, Client)

    seen: set[int] = set()
    clients: list[Client] = []
    for t in tasks:
        c = None
        if t.deal and t.deal.client:
            c = t.deal.client
        elif t.policy and t.policy.client:
            c = t.policy.client
        if c and c.id not in seen:
            seen.add(c.id)
            clients.append(c)
    return clients


def pop_next_by_client(chat_id: int, client_id: int) -> Task | None:
    """Выдать следующую задачу из очереди, фильтруя по клиенту."""
    with db.atomic():
        query = (
            Task.select(Task.id)
            .join(Deal, JOIN.LEFT_OUTER)
            .switch(Task)
            .join(Policy, JOIN.LEFT_OUTER)
            .where(
                (Task.dispatch_state == "queued")
                & (Task.is_deleted == False)
                & ((Deal.client_id == client_id) | (Policy.client_id == client_id))
            )
            .order_by(Task.queued_at.asc())
            .limit(1)
        )

        task_ids = [t.id for t in query]
        if not task_ids:
            logger.info("📭 Нет задач в очереди для клиента %s", client_id)
            return None

        base = Task.select().where(Task.id.in_(task_ids))
        task_list = prefetch(base, Deal, Policy, Client)
        task = task_list[0] if task_list else None

        if task:
            task.dispatch_state = "sent"
            task.tg_chat_id = chat_id
            task.save()
            if task.deal:
                refresh_deal_drive_link(task.deal)
            logger.info(
                "📬 Задача #%s выдана в Telegram для клиента %s: chat_id=%s",
                task.id,
                client_id,
                chat_id,
            )
        else:
            logger.info("📭 Нет задач в очереди для клиента %s", client_id)
        return task


def get_deals_with_queued_tasks(client_id: int) -> list[Deal]:
    """Вернуть сделки клиента, у которых есть задачи в очереди."""
    base = (
        Task.select()
        .join(Deal)
        .where(
            (Task.dispatch_state == "queued")
            & (Task.is_deleted == False)
            & (Deal.client_id == client_id)
        )
    )
    tasks = prefetch(base, Deal)

    seen: set[int] = set()
    deals: list[Deal] = []
    for t in tasks:
        if t.deal and t.deal.id not in seen:
            seen.add(t.deal.id)
            deals.append(t.deal)
    return deals


def get_all_deals_with_queued_tasks() -> list[Deal]:
    """Вернуть все сделки, у которых есть задачи в очереди."""
    base = (
        Task.select()
        .join(Deal)
        .where(
            (Task.dispatch_state == "queued") & (Task.is_deleted == False)
        )
    )
    tasks = prefetch(base, Deal, Client)

    seen: set[int] = set()
    deals: list[Deal] = []
    for t in tasks:
        if t.deal and t.deal.id not in seen:
            seen.add(t.deal.id)
            deals.append(t.deal)
    return deals


def pop_next_by_deal(chat_id: int, deal_id: int) -> Task | None:
    """Выдать следующую задачу из очереди для сделки."""
    with db.atomic():
        query = (
            Task.select(Task.id)
            .where(
                (Task.dispatch_state == "queued")
                & (Task.is_deleted == False)
                & (Task.deal_id == deal_id)
            )
            .order_by(Task.queued_at.asc())
            .limit(1)
        )

        task_ids = [t.id for t in query]
        if not task_ids:
            logger.info("📭 Нет задач в очереди для сделки %s", deal_id)
            return None

        base = Task.select().where(Task.id.in_(task_ids))
        task_list = prefetch(base, Deal, Policy, Client)
        task = task_list[0] if task_list else None

        if task:
            task.dispatch_state = "sent"
            task.tg_chat_id = chat_id
            task.save()
            if task.deal:
                refresh_deal_drive_link(task.deal)
            logger.info(
                "📬 Задача #%s выдана в Telegram для сделки %s: chat_id=%s",
                task.id,
                deal_id,
                chat_id,
            )
        else:
            logger.info("📭 Нет задач в очереди для сделки %s", deal_id)
        return task


def pop_all_by_deal(chat_id: int, deal_id: int) -> list[Task]:
    """Выдать все задачи из очереди для сделки."""
    with db.atomic():
        query = (
            Task.select(Task.id)
            .where(
                (Task.dispatch_state == "queued")
                & (Task.is_deleted == False)
                & (Task.deal_id == deal_id)
            )
            .order_by(Task.queued_at.asc())
        )

        task_ids = [t.id for t in query]
        if not task_ids:
            logger.info("📭 Нет задач в очереди для сделки %s", deal_id)
            return []

        base = Task.select().where(Task.id.in_(task_ids))
        task_list = list(prefetch(base, Deal, Policy, Client))

        for task in task_list:
            task.dispatch_state = "sent"
            task.tg_chat_id = chat_id
            task.save()
            if task.deal:
                refresh_deal_drive_link(task.deal)
            logger.info(
                "📬 Задача #%s выдана в Telegram для сделки %s: chat_id=%s",
                task.id,
                deal_id,
                chat_id,
            )
        return task_list


def pop_next(chat_id: int) -> Task | None:
    with db.atomic():
        query = (
            Task.select(Task.id)
            .where((Task.dispatch_state == "queued") & (Task.is_deleted == False))
            .order_by(Task.queued_at.asc())
            .limit(1)
        )

        task_ids = [t.id for t in query]
        if not task_ids:
            logger.info("📭 Нет задач в очереди")
            return None

        base = Task.select().where(Task.id.in_(task_ids))
        task_list = prefetch(base, Deal, Policy, Client)
        task = task_list[0] if task_list else None

        if task:
            task.dispatch_state = "sent"
            task.tg_chat_id = chat_id
            task.save()
            if task.deal:
                refresh_deal_drive_link(task.deal)
            logger.info("📬 Задача #%s выдана в Telegram: chat_id=%s", task.id, chat_id)
        else:
            logger.info("📭 Нет задач в очереди")
        return task


def return_to_queue(task_id: int):
    t = Task.get_or_none(Task.id == task_id, Task.is_deleted == False)
    if t and t.dispatch_state == "sent":
        t.dispatch_state = "queued"
        t.tg_chat_id = None
        t.tg_message_id = None
        t.queued_at = _dt.datetime.utcnow()
        t.save()
        logger.info("↩ Задача #%s возвращена в очередь", t.id)
        try:
            from services.telegram_service import notify_admin
            notify_admin(f"↩ Задача #{t.id} возвращена в очередь")
        except Exception:
            logger.debug("Failed to notify admin", exc_info=True)


def notify_task(task_id: int) -> None:
    """Переотправить уведомление исполнителю по задаче."""
    t = Task.get_or_none(Task.id == task_id, Task.is_deleted == False)
    if not t or t.is_done:
        return
    if t.dispatch_state == "sent":
        return_to_queue(task_id)
    elif t.dispatch_state == "idle":
        queue_task(task_id)


def link_telegram(task_id: int, chat_id: int, msg_id: int):
    (
        Task.update(tg_chat_id=chat_id, tg_message_id=msg_id)
        .where(Task.id == task_id)
        .execute()
    )
    logger.info("🔗 Telegram-связь установлена для задачи #%s", task_id)


def mark_done(task_id: int, note: str | None = None) -> None:
    """Отметить задачу выполненной и обновить связанные объекты.

    Если ``note`` не указана, в журнал попадут примечания из самой задачи.
    Информация о выполнении также добавляется в связанную сделку или полис,
    аналогично обновлению через основное приложение.
    """

    task = Task.get_or_none(Task.id == task_id)
    if not task:
        logger.warning("❗ Задача %s не найдена для завершения", task_id)
        return

    full_note = note if note is not None else task.note
    update_task(task, is_done=True, note=full_note)
    try:
        from services.telegram_service import notify_admin
        notify_admin(f"✅ Задача #{task.id} выполнена")
    except Exception:
        logger.debug("Failed to notify admin", exc_info=True)


def append_note(task_id: int, text: str):
    if not text.strip():
        return
    t = Task.get_or_none(Task.id == task_id)
    if t:
        t.note = ((t.note + "\n") if t.note else "") + text
        t.save()
        logger.info("🗒 К задаче #%s добавлена заметка", t.id)
        try:
            from services.telegram_service import notify_admin
            notify_admin(f"📝 Обновление по задаче #{t.id}: {text}")
        except Exception:
            logger.debug("Failed to notify admin", exc_info=True)


# ─────────────────────── постраничный вывод ─────────────────────
def build_task_query(
    include_done=True,
    include_deleted=False,
    search_text=None,
    only_queued=False,
    due_before=None,
    deal_id=None,
    policy_id=None,
    sort_field="due_date",
    sort_order="asc",
):
    query = Task.select()
    if not include_done:
        query = query.where(Task.is_done == False)
    if not include_deleted:
        query = query.where(Task.is_deleted == False)
    if only_queued:
        query = query.where(Task.dispatch_state == "queued")
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
    return query


def get_tasks_page(
    page: int, per_page: int, sort_field="due_date", sort_order="asc", **filters
):
    """Получить страницу задач.

    Args:
        page: Номер страницы.
        per_page: Количество задач на странице.
        sort_field: Поле сортировки.
        sort_order: Направление сортировки.
        **filters: Дополнительные фильтры.

    Returns:
        ModelSelect: Выборка задач.
    """
    logger.debug("🔽 Применяем сортировку: field=%s, order=%s", sort_field, sort_order)

    offset = (page - 1) * per_page
    query = build_task_query(**filters)

    if sort_field and hasattr(Task, sort_field):
        field = getattr(Task, sort_field)
        order = field.asc() if sort_order == "asc" else field.desc()
        query = query.order_by(order)
    else:
        query = query.order_by(Task.due_date.desc())

    return query.offset(offset).limit(per_page)


def get_pending_tasks_page(page: int, per_page: int):
    """Получить страницу невыполненных задач.

    Args:
        page: Номер страницы.
        per_page: Количество задач на странице.

    Returns:
        ModelSelect: Выборка задач.
    """
    offset = (page - 1) * per_page
    return (
        Task.select()
        .where((Task.is_done == False) & (Task.is_deleted == False))
        .offset(offset)
        .limit(per_page)
    )


def get_queued_tasks_by_deal(deal_id: int) -> list[Task]:
    """Вернуть задачи в очереди для указанной сделки."""
    policy_subq = (
        Policy.select(Policy.id)
        .where(Policy.deal_id == deal_id)
    )

    base = (
        Task.select()
        .where(
            (Task.dispatch_state == "queued")
            & (Task.is_deleted == False)
            & (
                (Task.deal_id == deal_id)
                | (Task.policy_id.in_(policy_subq))
            )
        )
    )
    return list(prefetch(base, Deal, Policy, Client))


def get_all_queued_tasks() -> list[Task]:
    """Вернуть все задачи в состоянии ``queued`` с предзагрузкой связей."""
    base = (
        Task.select()
        .where((Task.dispatch_state == "queued") & (Task.is_deleted == False))
        .order_by(Task.queued_at.asc())
    )
    return list(prefetch(base, Deal, Policy, Client))


def pop_task_by_id(chat_id: int, task_id: int) -> Task | None:
    """Выдать задачу по id, если она в очереди."""
    with db.atomic():
        task = (
            Task.select()
            .where(
                (Task.id == task_id)
                & (Task.is_deleted == False)
                & (Task.dispatch_state == "queued")
            )
            .first()
        )
        if not task:
            return None

        task.dispatch_state = "sent"
        task.tg_chat_id = chat_id
        task.save()

        result = list(prefetch(Task.select().where(Task.id == task.id), Deal, Policy, Client))
        task = result[0] if result else None
        if task and task.deal:
            refresh_deal_drive_link(task.deal)
        return task


def unassign_from_telegram(task_id: int) -> None:
    task = Task.get_by_id(task_id)
    task.dispatch_state = "idle"
    task.tg_chat_id = None
    task.tg_message_id = None
    task.save()
    logger.info("❎ Задача #%s снята с Telegram", task.id)


def get_tasks_by_deal(deal_id: int) -> list[Task]:
    """Получить задачи, связанные со сделкой.

    Args:
        deal_id: Идентификатор сделки.

    Returns:
        list[Task]: Список задач сделки.
    """
    policy_subq = (
        Policy.select(Policy.id)
        .where(Policy.deal_id == deal_id)
    )

    return Task.select().where(
        (
            (Task.deal_id == deal_id)
            | (Task.policy_id.in_(policy_subq))
        )
        & (Task.is_deleted == False)
    )


def get_incomplete_tasks_by_deal(deal_id: int) -> list[Task]:
    """Получить невыполненные задачи сделки с предзагрузкой связей."""
    policy_subq = (
        Policy.select(Policy.id)
        .where(Policy.deal_id == deal_id)
    )

    base = (
        Task.select()
        .where(
            (
                (Task.deal_id == deal_id)
                | (Task.policy_id.in_(policy_subq))
            )
            & (Task.is_deleted == False)
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

    # Полисы могут быть связаны со сделкой, даже если сама задача создана
    # только для полиса. Поэтому дополнительно выбираем задачи, у которых
    # ``policy.deal_id`` относится к нужному исполнителю.
    policy_subq = (
        Policy.select(Policy.id)
        .where(Policy.deal_id.in_(deal_ids))
    )

    base = (
        Task.select()
        .where(
            (
                (Task.deal_id.in_(deal_ids)) |
                (Task.policy_id.in_(policy_subq))
            )
            & (Task.is_deleted == False)
            & (Task.is_done == False)
        )
    )
    return list(prefetch(base, Deal, Client, Policy))
