"""Функции для получения сводной информации на дашборд."""

from datetime import date, timedelta
from functools import lru_cache

from peewee import ModelSelect, fn
from playhouse.shortcuts import prefetch

from database.models import Client, Deal, Policy, Task
from .task_states import SENT


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
        .where((Task.dispatch_state == SENT) & (Task.is_done == False))
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
    policy_query = _policy_dashboard_select()
    return list(prefetch(base, Deal, policy_query, Client))


def get_expiring_policies(limit: int = 10) -> list[Policy]:
    """Полисы, срок действия которых скоро заканчивается."""
    base = (
        _policy_dashboard_select()
        .where(
            (Policy.is_deleted == False)
            & (Policy.end_date.is_null(False))
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


@lru_cache(maxsize=1)
def _policy_dashboard_fields() -> tuple:
    """Набор полей ``Policy`` без необязательных Drive-колонок."""
    columns = {
        column.name
        for column in Policy._meta.database.get_columns(Policy._meta.table_name)
    }

    base_fields: tuple = (
        Policy.id,
        Policy.client,
        Policy.deal,
        Policy.policy_number,
        Policy.note,
        Policy.start_date,
        Policy.end_date,
        Policy.renewed_to,
        Policy.is_deleted,
    )
    optional_fields = tuple(
        getattr(Policy, field_name)
        for field_name in ("drive_folder_path", "drive_folder_link")
        if field_name in columns
    )
    return base_fields + optional_fields


def _policy_dashboard_select() -> ModelSelect:
    """Запрос на выборку полей ``Policy`` с проверкой наличия Drive-колонок."""
    return Policy.select(*_policy_dashboard_fields())
