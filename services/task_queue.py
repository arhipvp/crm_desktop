"""Функции для работы с очередью задач."""

import datetime as _dt
import logging

from peewee import JOIN
from playhouse.shortcuts import prefetch

from database.db import db
from database.models import Client, Deal, Policy, Task
from services.deal_service import refresh_deal_drive_link


logger = logging.getLogger(__name__)


def queue_task(task_id: int):
    """Поставить задачу в очередь (idle → queued)."""
    with db.atomic():
        t = Task.active().where(Task.id == task_id).get_or_none()
        if t and t.dispatch_state == "idle":
            t.dispatch_state = "queued"
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
    base = Task.active().where(Task.dispatch_state == "queued")
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
            Task.active()
            .select(Task.id)
            .join(Deal, JOIN.LEFT_OUTER)
            .switch(Task)
            .join(Policy, JOIN.LEFT_OUTER)
            .where(
                (Task.dispatch_state == "queued")
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
        Task.active()
        .join(Deal)
        .where((Task.dispatch_state == "queued") & (Deal.client_id == client_id))
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
    base = Task.active().join(Deal).where(Task.dispatch_state == "queued")
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
            Task.active()
            .select(Task.id)
            .where(
                (Task.dispatch_state == "queued") & (Task.deal_id == deal_id)
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
            Task.active()
            .select(Task.id)
            .where(
                (Task.dispatch_state == "queued") & (Task.deal_id == deal_id)
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
            Task.active()
            .select(Task.id)
            .where(Task.dispatch_state == "queued")
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
    with db.atomic():
        t = Task.active().where(Task.id == task_id).get_or_none()
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
            (Task.dispatch_state == "queued")
            & ((Task.deal_id == deal_id) | (Task.policy_id.in_(policy_subq)))
        )
    )
    return list(prefetch(base, Deal, Policy, Client))


def get_all_queued_tasks() -> list[Task]:
    """Вернуть все задачи в состоянии ``queued`` с предзагрузкой связей."""
    base = (
        Task.active()
        .where(Task.dispatch_state == "queued")
        .order_by(Task.queued_at.asc())
    )
    return list(prefetch(base, Deal, Policy, Client))


def pop_task_by_id(chat_id: int, task_id: int) -> Task | None:
    """Выдать задачу по id, если она в очереди."""
    with db.atomic():
        task = (
            Task.active()
            .where((Task.id == task_id) & (Task.dispatch_state == "queued"))
            .first()
        )
        if not task:
            return None

        task.dispatch_state = "sent"
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

