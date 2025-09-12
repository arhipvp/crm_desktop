"""Сервисные функции для учёта доходов."""

import logging
from typing import Any
from decimal import Decimal

from peewee import JOIN, Field
from peewee import SqliteDatabase
from database.db import db
from database.models import Client, Income, Payment, Policy, Deal, Executor, DealExecutor
from services.payment_service import get_payment_by_id
from services import executor_service as es
from services.telegram_service import notify_executor

logger = logging.getLogger(__name__)

# ──────────────────────── вспомогательные утилиты ────────────────────────

def get_income_highlight_color(income: Income) -> str | None:
    """Вернуть цвет подсветки строки дохода.

    Если у связанного полиса указан контрагент, возвращается розовый цвет
    ``"#ffcccc"``. В противном случае возвращается ``None``.
    """

    payment = getattr(income, "payment", None)
    policy = getattr(payment, "policy", None) if payment else None
    contractor = getattr(policy, "contractor", "") if policy else ""
    if contractor and contractor.strip():
        return "#ffcccc"
    return None

# ───────────────────────── базовые CRUD ─────────────────────────

def get_all_incomes():
    """Вернуть все доходы без удалённых."""
    return Income.active()


def get_pending_incomes():
    """Доходы, которые ещё не получены."""
    return Income.active().where(Income.received_date.is_null(True))


def get_income_counts_by_deal_id(deal_id: int) -> tuple[int, int]:
    """Подсчитать количество открытых и закрытых доходов по сделке."""
    base = (
        Income.active()
        .join(Payment)
        .join(Policy)
        .where(Policy.deal_id == deal_id)
    )
    open_count = base.where(Income.received_date.is_null(True)).count()
    closed_count = base.where(Income.received_date.is_null(False)).count()
    return open_count, closed_count


def get_income_by_id(income_id: int):
    """Получить доход по идентификатору."""
    return Income.get_or_none(Income.id == income_id)


def mark_income_deleted(income_id: int):
    income = Income.get_or_none(Income.id == income_id)
    if income:
        income.soft_delete()
    else:
        logger.warning("❗ Доход с id=%s не найден для удаления", income_id)


def mark_incomes_deleted(income_ids: list[int]) -> int:
    """Массово пометить доходы удалёнными."""
    if not income_ids:
        return 0
    return (
        Income.update(is_deleted=True)
        .where(Income.id.in_(income_ids))
        .execute()
    )


def get_incomes_page(
    page: int,
    per_page: int,
    order_by: str | Any = "received_date",
    order_dir: str = "desc",
    search_text: str = "",
    show_deleted: bool = False,
    include_received: bool = True,
    received_date_range=None,
    column_filters: dict | None = None,
    *,
    only_received: bool = False,
    join_executor: bool | None = None,
    **kwargs,
):
    """Получить страницу доходов по фильтрам."""
    if join_executor is None:
        join_executor = (
            isinstance(order_by, Field)
            and getattr(order_by, "model", None) is Executor
        )

    query = build_income_query(
        search_text=search_text,
        show_deleted=show_deleted,
        include_received=include_received,
        received_date_range=received_date_range,
        column_filters=column_filters,
        only_received=only_received,
        join_executor=join_executor,
        **kwargs,
    )
    logger.debug(
        "\U0001F50E built income query. join_executor=%s order_by=%s order_dir=%s",
        join_executor,
        getattr(order_by, 'name', order_by),
        order_dir,
    )

    # --- сортировка ---
    if isinstance(order_by, str):
        if hasattr(Income, order_by):
            field = getattr(Income, order_by)
        else:
            field = Income.received_date
    else:
        field = order_by

    order_fields = []
    if (
        column_filters
        and Executor.full_name in column_filters
        and not isinstance(db.obj, SqliteDatabase)
    ):
        order_fields.append(Income.id)
    order_fields.append(field.desc() if order_dir == "desc" else field.asc())
    query = query.order_by(*order_fields)
    logger.debug("\U0001F4DD final SQL: %s", query.sql())

    offset = (page - 1) * per_page
    return query.limit(per_page).offset(offset)

# Уведомления
def _notify_income_received(income: Income) -> None:
    payment = income.payment
    if not payment:
        return
    policy = payment.policy
    if not policy or not policy.deal_id:
        return
    ex = es.get_executor_for_deal(policy.deal_id)
    if not ex or not es.is_approved(ex.tg_id):
        return
    deal = policy.deal
    desc = f" — {deal.description}" if deal and deal.description else ""
    text = (
        f"💰 По вашей сделке #{deal.id}{desc} поступило вознаграждение {income.amount:g} по полису {policy.policy_number}"
    )
    notify_executor(ex.tg_id, text)


# ─────────────────────────── Добавление ───────────────────────────

def add_income(**kwargs):
    """Создать запись дохода по платежу."""
    payment = kwargs.get("payment") or get_payment_by_id(kwargs.get("payment_id"))
    if not payment:
        raise ValueError("Не найден платёж")

    amount = kwargs.get("amount")
    if amount is None:
        raise ValueError("Поле amount обязательно")

    allowed_fields = {"amount", "received_date", "commission_source"}

    clean_data = {
        field: kwargs[field]
        for field in allowed_fields
        if field in kwargs and kwargs[field] not in ("", None)
    }
    if "amount" in clean_data:
        clean_data["amount"] = Decimal(str(clean_data["amount"]))

    try:
        with db.atomic():
            income = Income.create(payment=payment, **clean_data)
    except Exception as e:
        logger.error("❌ Ошибка при создании дохода: %s", e)
        raise

    if income.received_date:
        _notify_income_received(income)
    return income


# ─────────────────────────── Обновление ───────────────────────────

def update_income(income: Income, **kwargs):
    """Обновить запись дохода."""
    allowed_fields = {
        "payment",
        "payment_id",
        "amount",
        "received_date",
        "commission_source",
    }

    updates = {}

    for key in allowed_fields:
        if key in kwargs:
            value = kwargs[key]
            if key == "payment_id" and not kwargs.get("payment"):
                value = get_payment_by_id(value)
                key = "payment"
            if key == "amount" and value is not None:
                value = Decimal(str(value))
            updates[key] = value

    if not updates:
        return income

    old_received = income.received_date
    with db.atomic():
        for key, value in updates.items():
            setattr(income, key, value)
        logger.debug("💬 update_income: received_date=%r", updates.get("received_date"))
        logger.debug("💬 final obj: income.received_date = %r", income.received_date)
        income.save()

    if old_received is None and income.received_date:
        _notify_income_received(income)
    return income


def apply_income_filters(
    query,
    search_text="",
    include_received=True,
    received_date_range=None,
    deal_id=None,
    column_filters: dict | None = None,
    *,
    only_received: bool = False,
    join_executor: bool = False,
):
    if search_text:
        query = query.where(
            (Policy.policy_number.contains(search_text))
            | (Client.name.contains(search_text))
            | (Deal.description.contains(search_text))
            | (Policy.note.contains(search_text))
        )
    if only_received:
        query = query.where(Income.received_date.is_null(False))
    elif not include_received:
        query = query.where(Income.received_date.is_null(True))
    if received_date_range:
        date_from, date_to = received_date_range
        if date_from:
            query = query.where(Income.received_date >= date_from)
        if date_to:
            query = query.where(Income.received_date <= date_to)
    if deal_id:
        query = query.where(Policy.deal_id == deal_id)

    from services.query_utils import apply_column_filters, apply_field_filters

    logger.debug(
        "\U0001F50D apply_income_filters: col_filters=%s", column_filters
    )

    field_filters = {}
    name_filters = {}
    if column_filters:
        for key, val in column_filters.items():
            if isinstance(key, Field):
                field_filters[key] = val
            else:
                name_filters[str(key)] = val

    if Executor.full_name in field_filters or join_executor:
        query = (
            query.switch(Deal)
            .join(
                DealExecutor,
                JOIN.LEFT_OUTER,
                on=(DealExecutor.deal == Deal.id),
            )
            .join(
                Executor,
                JOIN.LEFT_OUTER,
                on=(DealExecutor.executor == Executor.id),
            )
        )
        if isinstance(db.obj, SqliteDatabase):
            query = query.distinct()
        else:
            query = query.distinct(Income.id)

    query = apply_field_filters(query, field_filters)
    query = apply_column_filters(query, name_filters, Income)
    return query


def build_income_query(
    search_text: str = "",
    show_deleted: bool = False,
    include_received: bool = True,
    received_date_range=None,
    column_filters: dict[str, str] | None = None,
    *,
    only_received: bool = False,
    join_executor: bool = False,
    **kwargs,
):
    base = Income.active() if not show_deleted else Income.select()
    query = (
        base
        .select(Income, Payment, Policy, Client, Deal)
        .join(Payment, on=(Income.payment == Payment.id))
        .switch(Payment)
        .join(Policy, on=(Payment.policy == Policy.id))
        .switch(Policy)
        .join(Client, on=(Policy.client == Client.id))
        .switch(Policy)
        .join(Deal, JOIN.LEFT_OUTER, on=(Policy.deal == Deal.id))
    )

    query = apply_income_filters(
        query=query,
        search_text=search_text,
        include_received=include_received,
        received_date_range=received_date_range,
        deal_id=kwargs.get("deal_id"),
        column_filters=column_filters,
        only_received=only_received,
        join_executor=join_executor,
    )

    return query


def create_stub_income(deal_id: int | None = None) -> Income:
    from services.payment_service import get_all_payments

    payments = get_all_payments()
    if deal_id:
        payments = [p for p in payments if p.policy and p.policy.deal_id == deal_id]
    if not payments:
        raise ValueError("Нет доступных платежей")
    return Income(payment=payments[0])
