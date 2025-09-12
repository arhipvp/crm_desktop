"""Функции для работы с очередью задач."""

import datetime as _dt
import logging

from peewee import JOIN
from playhouse.shortcuts import prefetch

from database.db import db
from database.models import Client, Deal, Policy, Task
from services.deal_service import refresh_deal_drive_link
from .task_states import IDLE, QUEUED, SENT


logger = logging.getLogger(__name__)


def queue_task(task_id: int):
    """Поставить задачу в очередь (idle → queued)."""
    with db.atomic():
        t = Task.active().where(Task.id == task_id).get_or_none()
        if t and t.dispatch_state == IDLE:
            t.dispatch_state = QUEUED
            t.queued_at = _dt.datetime.utcnow()
            t.save()
            logger.info("📤 Задача #%s поставлена в очередь", t.id)
            try:
                from services.telegram_service import notify_admin

                notify_admin(f"📤 Задача #{t.id} поставлена в очередь")
            except Exception:  # pragma: no cover - logging
                logger.debug("Failed to notify admin", exc_info=True)
        elif t:
            logger.info(
                "⏭ Задача #%s не поставлена в очередь: состояние %s",
                t.id,
                t.dispatch_state,
            )


def get_clients_with_queued_tasks() -> list[Client]:
    """Вернуть уникальных клиентов с задачами в состоянии ``queued``."""
    deal_clients = (
        Client.select()
        .distinct()
        .join(Deal)
        .join(Task)
        .where((Task.dispatch_state == QUEUED) & (Task.is_deleted == False))
    )
    policy_clients = (
        Client.select()
        .distinct()
        .join(Policy)
        .join(Task)
        .where((Task.dispatch_state == QUEUED) & (Task.is_deleted == False))
    )
    return list(deal_clients.union(policy_clients))


def _dispatch_tasks(
    filter_cond,
    chat_id: int,
    log_suffix: str,
    limit: int | None = 1,
) -> list[Task]:
    """Выбрать задачи из очереди по условию и отметить как отправленные.

    Parameters:
        filter_cond: Дополнительное условие фильтрации задач.
        chat_id: Идентификатор чата Telegram, куда отправляются задачи.
        log_suffix: Суффикс для сообщений журнала.
        limit: Максимальное количество выдаваемых задач, ``None`` — без
            ограничения.
    """
    with db.atomic():
        query = (
            Task.active()
            .select(Task.id)
            .join(Deal, JOIN.LEFT_OUTER)
            .switch(Task)
            .join(Policy, JOIN.LEFT_OUTER)
        )
        where_expr = Task.dispatch_state == QUEUED
        if filter_cond is not None:
            where_expr &= filter_cond
        query = query.where(where_expr).order_by(Task.queued_at.asc())
        if limit is not None:
            query = query.limit(limit)

        task_ids = list(dict.fromkeys(t.id for t in query))
        if not task_ids:
            logger.info("📭 Нет задач в очереди%s", log_suffix)
            return []

        base = Task.select().where(Task.id.in_(task_ids))
        task_list = list(prefetch(base, Deal, Policy, Client))
        for task in task_list:
            task.dispatch_state = SENT
            task.tg_chat_id = chat_id
            task.save()
            if task.deal:
                refresh_deal_drive_link(task.deal)
            logger.info(
                "📬 Задача #%s выдана в Telegram%s: chat_id=%s",
                task.id,
                log_suffix,
                chat_id,
            )
        return task_list


def pop_next_by_client(chat_id: int, client_id: int) -> Task | None:
    """Выдать следующую задачу из очереди, фильтруя по клиенту."""
    tasks = _dispatch_tasks(
        (Deal.client_id == client_id) | (Policy.client_id == client_id),
        chat_id,
        f" для клиента {client_id}",
        limit=1,
    )
    return tasks[0] if tasks else None


def get_deals_with_queued_tasks(client_id: int) -> list[Deal]:
    """Вернуть сделки клиента, у которых есть задачи в очереди."""
    base = (
        Deal.select()
        .distinct()
        .join(Task)
        .where(
            (Task.dispatch_state == QUEUED)
            & (Task.is_deleted == False)
            & (Deal.client_id == client_id)
        )
    )
    return list(prefetch(base, Client))


def get_all_deals_with_queued_tasks() -> list[Deal]:
    """Вернуть все сделки, у которых есть задачи в очереди."""
    base = (
        Deal.select()
        .distinct()
        .join(Task)
        .where((Task.dispatch_state == QUEUED) & (Task.is_deleted == False))
    )
    return list(prefetch(base, Client))


def pop_next_by_deal(chat_id: int, deal_id: int) -> Task | None:
    """Выдать следующую задачу из очереди для сделки."""
    tasks = _dispatch_tasks(
        Task.deal_id == deal_id,
        chat_id,
        f" для сделки {deal_id}",
        limit=1,
    )
    return tasks[0] if tasks else None


def pop_all_by_deal(chat_id: int, deal_id: int) -> list[Task]:
    """Выдать все задачи из очереди для сделки."""
    return _dispatch_tasks(
        Task.deal_id == deal_id,
        chat_id,
        f" для сделки {deal_id}",
        limit=None,
    )


def pop_next(chat_id: int) -> Task | None:
    tasks = _dispatch_tasks(None, chat_id, "", limit=1)
    return tasks[0] if tasks else None


def return_to_queue(task_id: int):
    with db.atomic():
        t = Task.active().where(Task.id == task_id).get_or_none()
        if t and t.dispatch_state == SENT:
            t.dispatch_state = QUEUED
            t.tg_chat_id = None
            t.tg_message_id = None
            t.queued_at = _dt.datetime.utcnow()
            t.save()
            logger.info("↩ Задача #%s возвращена в очередь", t.id)
            try:
                from services.telegram_service import notify_admin

                notify_admin(f"↩ Задача #{t.id} возвращена в очередь")
            except Exception:  # pragma: no cover - logging
                logger.debug("Failed to notify admin", exc_info=True)


def get_queued_tasks_by_deal(deal_id: int) -> list[Task]:
    """Вернуть задачи в очереди для указанной сделки."""
    policy_subq = (
        Policy.select(Policy.id)
        .where(Policy.deal_id == deal_id)
    )

    base = (
        Task.active()
        .where(
            (Task.dispatch_state == QUEUED)
            & ((Task.deal_id == deal_id) | (Task.policy_id.in_(policy_subq)))
        )
    )
    return list(prefetch(base, Deal, Policy, Client))


def get_all_queued_tasks() -> list[Task]:
    """Вернуть все задачи в состоянии ``queued`` с предзагрузкой связей."""
    base = (
        Task.active()
        .where(Task.dispatch_state == QUEUED)
        .order_by(Task.queued_at.asc())
    )
    return list(prefetch(base, Deal, Policy, Client))


def pop_task_by_id(chat_id: int, task_id: int) -> Task | None:
    """Выдать задачу по id, если она в очереди."""
    with db.atomic():
        task = (
            Task.active()
            .where((Task.id == task_id) & (Task.dispatch_state == QUEUED))
            .first()
        )
        if not task:
            return None

        task.dispatch_state = SENT
        task.tg_chat_id = chat_id
        task.save()

        result = list(
            prefetch(Task.select().where(Task.id == task.id), Deal, Policy, Client)
        )
        task = result[0] if result else None
        if task and task.deal:
            refresh_deal_drive_link(task.deal)
        return task


__all__ = [
    "queue_task",
    "get_clients_with_queued_tasks",
    "pop_next_by_client",
    "get_deals_with_queued_tasks",
    "get_all_deals_with_queued_tasks",
    "pop_next_by_deal",
    "pop_all_by_deal",
    "pop_next",
    "return_to_queue",
    "get_queued_tasks_by_deal",
    "get_all_queued_tasks",
    "pop_task_by_id",
]

