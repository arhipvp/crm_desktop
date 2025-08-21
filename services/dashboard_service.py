"""Функции для получения сводной информации на дашборд."""

from playhouse.shortcuts import prefetch
from peewee import fn
from datetime import date, timedelta

from database.models import Client, Deal, Policy, Task


def get_basic_stats() -> dict:
    """Получить общее количество записей по основным сущностям."""
    return {
        "clients": Client.active().count(),
        "deals": Deal.active().count(),
        "policies": Policy.active().count(),
        "tasks": Task.active().count(),
    }


def count_assistant_tasks() -> int:
    """Количество задач, отправленных ассистенту в Telegram."""
    return (
        Task.active()
        .where((Task.dispatch_state == "sent") & (Task.is_done == False))
        .count()
    )


def count_sent_tasks() -> int:
    """Количество задач, отправленных в Telegram (по ``queued_at``)."""
    return (
        Task.active().where(Task.queued_at.is_null(False)).count()
    )


def count_working_tasks() -> int:
    """Количество задач, находящихся у помощника в работе."""
    return (
        Task.active().where(Task.tg_chat_id.is_null(False)).count()
    )


def count_unconfirmed_tasks() -> int:
    """Количество задач с заметкой, но не подтверждённых пользователем."""
    return (
        Task.active()
        .where(Task.note.is_null(False) & (Task.is_done == False))
        .count()
    )


def get_upcoming_tasks(limit: int = 10) -> list[Task]:
    """Ближайшие невыполненные задачи."""
    base = (
        Task.active()
        .where(Task.is_done == False)
        .order_by(Task.due_date.asc())
        .limit(limit)
    )
    return list(prefetch(base, Deal, Policy, Client))


def get_expiring_policies(limit: int = 10) -> list[Policy]:
    """Полисы, срок действия которых скоро заканчивается."""
    base = (
        Policy.active()
        .where(
            (Policy.end_date.is_null(False))
            & (
                Policy.renewed_to.is_null(True)
                | (Policy.renewed_to == "")
                | (Policy.renewed_to == "Нет")
            )
        )
        .order_by(Policy.end_date.asc())
        .limit(limit)
    )
    return list(prefetch(base, Client, Deal))


def get_upcoming_deal_reminders(limit: int = 10) -> list[Deal]:
    """Ближайшие напоминания по открытым сделкам."""
    base = (
        Deal.active()
        .where(
            (Deal.is_closed == False)
            & (Deal.reminder_date.is_null(False))
        )
        .order_by(Deal.reminder_date.asc())
        .limit(limit)
    )
    return list(prefetch(base, Client))


def get_deal_reminder_counts(days: int = 14) -> dict:
    """Количество напоминаний по сделкам на ближайшие ``days`` дней."""
    today = date.today()
    # Включаем все дни в диапазоне, даже если напоминаний нет
    counts = {today + timedelta(days=i): 0 for i in range(days)}
    end_date = today + timedelta(days=days - 1)

    query = (
        Deal.active()
        .select(Deal.reminder_date, fn.COUNT(Deal.id).alias("cnt"))
        .where(
            (Deal.is_closed == False)
            & (Deal.reminder_date.is_null(False))
            & (Deal.reminder_date.between(today, end_date))
        )
        .group_by(Deal.reminder_date)
        .order_by(Deal.reminder_date.asc())
    )

    for row in query:
        counts[row.reminder_date] = row.cnt

    return counts
