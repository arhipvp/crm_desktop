"""Сервис работы с расходами."""

import logging
from decimal import Decimal
from typing import Any

from peewee import Field, JOIN, fn

from database.db import db
from database.models import Client, Deal, Expense, Income, Payment, Policy
from services.payment_service import get_payment_by_id
from services.query_utils import apply_search_and_filters

logger = logging.getLogger(__name__)

income_subquery = (
    Income.select(
        Income.payment_id.alias("payment_id"),
        fn.COALESCE(fn.SUM(Income.amount), 0).alias("income_total"),
    )
    .group_by(Income.payment_id)
    .alias("income_subquery")
)

expense_subquery = (
    Expense.select(
        Expense.payment_id.alias("payment_id"),
        fn.COALESCE(fn.SUM(Expense.amount), 0).alias("expense_total"),
    )
    .group_by(Expense.payment_id)
    .alias("expense_subquery")
)

income_total_expr = fn.COALESCE(income_subquery.c.income_total, 0)
expense_total_expr = fn.COALESCE(expense_subquery.c.expense_total, 0)
INCOME_TOTAL = income_total_expr.alias("income_total")
OTHER_EXPENSE_TOTAL = (expense_total_expr - Expense.amount).alias("other_expense_total")
net_income_expr = income_total_expr - expense_total_expr
NET_INCOME = net_income_expr.alias("net_income")
CONTRACTOR_PAYMENT = (net_income_expr * Decimal("0.2")).alias("contractor_payment")

# ─────────────────────────── CRUD ────────────────────────────


def get_all_expenses():
    """Вернуть все расходы без пометки удаления."""
    return Expense.active()


def get_pending_expenses():
    """Расходы без даты списания."""
    return Expense.active().where(Expense.expense_date.is_null(True))


def get_expense_counts_by_deal_id(deal_id: int) -> tuple[int, int]:
    """Подсчитать количество открытых и закрытых расходов по сделке."""
    base = Expense.active().join(Payment).join(Policy).where(Policy.deal_id == deal_id)
    open_count = base.where(Expense.expense_date.is_null(True)).count()
    closed_count = base.where(Expense.expense_date.is_null(False)).count()
    return open_count, closed_count


def get_expense_by_id(expense_id: int) -> Expense | None:
    """Получить расход по идентификатору."""
    return Expense.get_or_none(Expense.id == expense_id)


def mark_expense_deleted(expense_id: int):
    expense = Expense.get_or_none(Expense.id == expense_id)
    if expense:
        expense.soft_delete()
        logger.info("🗑️ Расход id=%s помечен удалённым", expense.id)
    else:
        logger.warning("❗ Расход с id=%s не найден для удаления", expense_id)


def mark_expenses_deleted(expense_ids: list[int]) -> int:
    """Массово пометить расходы удалёнными."""
    if not expense_ids:
        return 0
    return Expense.update(is_deleted=True).where(Expense.id.in_(expense_ids)).execute()


# ─────────────────────────── Добавление ───────────────────────────


def add_expense(**kwargs):
    """Создать запись расхода по платежу.

    Args:
        **kwargs: Поля расхода, включая ``payment`` или ``payment_id``,
            сумму ``amount`` и тип ``expense_type``.

    Returns:
        Expense: Созданная запись расхода.
    """
    payment = kwargs.get("payment") or get_payment_by_id(kwargs.get("payment_id"))
    if not payment:
        raise ValueError("Платёж не найден")
    if not payment.policy_id:
        raise ValueError("У платежа не указан связанный полис")

    amount = kwargs.get("amount")
    expense_type = kwargs.get("expense_type")
    if amount is None or not expense_type:
        raise ValueError("Обязательные поля: amount и expense_type")

    allowed_fields = {"amount", "expense_type", "expense_date", "note"}

    clean_data = {
        field: kwargs[field]
        for field in allowed_fields
        if field in kwargs and kwargs[field] not in ("", None)
    }
    if "amount" in clean_data:
        clean_data["amount"] = Decimal(str(clean_data["amount"]))

    try:
        with db.atomic():
            expense = Expense.create(
                payment=payment, policy_id=payment.policy_id, **clean_data
            )
        logger.info("✅ Расход id=%s создан", expense.id)
        return expense
    except Exception as e:
        logger.error("❌ Ошибка при создании расхода: %s", e)
        raise


# ─────────────────────────── Обновление ───────────────────────────


def update_expense(expense: Expense, **kwargs):
    """Обновить информацию о расходе.

    Args:
        expense: Изменяемый расход.
        **kwargs: Поля ``amount``, ``expense_type`` и др.

    Returns:
        Expense: Обновлённый расход.
    """
    allowed_fields = {"amount", "expense_type", "expense_date", "note"}

    with db.atomic():
        updates: dict[str, object] = {}
        for key, value in kwargs.items():
            if key in allowed_fields and value not in ("", None):
                if key == "amount":
                    value = Decimal(str(value))
                updates[key] = value

        payment_obj = None
        if kwargs.get("payment") is not None or kwargs.get("payment_id") is not None:
            payment_id = kwargs.get("payment_id")
            if kwargs.get("payment") is not None:
                payment_id = getattr(kwargs.get("payment"), "id", kwargs.get("payment"))
            payment_obj = get_payment_by_id(payment_id)
            if not payment_obj:
                raise ValueError("Платёж не найден")
            if not payment_obj.policy_id:
                raise ValueError("У платежа не указан связанный полис")
            expense.payment = payment_obj
            expense.policy = payment_obj.policy

        if not updates and not payment_obj:
            return expense

        log_updates: dict[str, Any] = {}
        for key, value in updates.items():
            if hasattr(value, "id"):
                log_updates[key] = value.id
            elif isinstance(value, Decimal):
                log_updates[key] = str(value)
            else:
                log_updates[key] = value
        if payment_obj:
            log_updates["payment"] = payment_obj.id
            log_updates["policy"] = payment_obj.policy_id

        for key, value in updates.items():
            setattr(expense, key, value)
        expense.save()
        logger.info("✏️ Расход id=%s обновлён: %s", expense.id, log_updates)
        return expense


# ──────────────────────── Постраничный вывод ───────────────────────


def get_expenses_page(
    page: int,
    per_page: int,
    *,
    search_text: str = "",
    show_deleted: bool = False,
    deal_id: int = None,
    include_paid: bool = True,
    expense_date_range=None,
    column_filters: dict | None = None,
    order_by: str | Field = Expense.expense_date,
    order_dir: str = "desc",
):
    """Вернуть страницу расходов с фильтрами.

    Args:
        page: Номер страницы.
        per_page: Количество записей на странице.
        search_text: Строка поиска по полисам и клиентам.
        show_deleted: Учитывать удалённые записи.
        deal_id: Идентификатор сделки для фильтра.
        include_paid: Показывать оплаченные расходы.
        expense_date_range: Период дат выплат (start, end).
        column_filters: Фильтры по столбцам.
        order_by: Поле сортировки.
        order_dir: Направление сортировки ("asc" или "desc").

    Returns:
        ModelSelect: Выборка расходов.
    """
    query = build_expense_query(
        search_text=search_text,
        show_deleted=show_deleted,
        deal_id=deal_id,
        include_paid=include_paid,
        expense_date_range=expense_date_range,
        column_filters=column_filters,
        order_by=order_by,
        order_dir=order_dir,
    )
    offset = (page - 1) * per_page
    return query.limit(per_page).offset(offset)


def apply_expense_filters(
    query,
    search_text=None,
    deal_id=None,
    include_paid=True,
    expense_date_range=None,
    column_filters: dict | None = None,
    **kwargs,
):
    if deal_id:
        query = query.where(Policy.deal_id == deal_id)
    extra_fields = [
        Policy.policy_number,
        Client.name,
        Deal.description,
        Policy.note,
    ]

    col_filters = dict(column_filters or {})
    income_total_filter = col_filters.pop(INCOME_TOTAL, None)
    if income_total_filter is None and Income.amount in col_filters:
        income_total_filter = col_filters.pop(Income.amount)
    other_expense_total_filter = col_filters.pop(OTHER_EXPENSE_TOTAL, None)
    net_income_filter = col_filters.pop(NET_INCOME, None)
    contractor_payment_filter = col_filters.pop(CONTRACTOR_PAYMENT, None)

    query = apply_search_and_filters(
        query, Expense, search_text or "", col_filters, extra_fields
    )

    if not include_paid:
        query = query.where(Expense.expense_date.is_null(True))
    if expense_date_range:
        date_from, date_to = expense_date_range
        if date_from:
            query = query.where(Expense.expense_date >= date_from)
        if date_to:
            query = query.where(Expense.expense_date <= date_to)

    if income_total_filter:
        query = query.having(INCOME_TOTAL.cast("TEXT").contains(income_total_filter))
    if other_expense_total_filter:
        query = query.having(
            OTHER_EXPENSE_TOTAL.cast("TEXT").contains(other_expense_total_filter)
        )
    if net_income_filter:
        query = query.having(NET_INCOME.cast("TEXT").contains(net_income_filter))
    if contractor_payment_filter:
        query = query.having(
            CONTRACTOR_PAYMENT.cast("TEXT").contains(contractor_payment_filter)
        )

    return query


def build_expense_query(
    search_text=None,
    show_deleted=False,
    deal_id=None,
    include_paid=True,
    expense_date_range=None,
    column_filters: dict | None = None,
    order_by: str | Field | None = None,
    order_dir: str = "desc",
    **kwargs,
):
    base = Expense.active() if not show_deleted else Expense.select()
    query = (
        base.select(
            Expense,
            Payment,
            Policy,
            Client,
            Deal,
            INCOME_TOTAL,
            OTHER_EXPENSE_TOTAL,
            NET_INCOME,
            CONTRACTOR_PAYMENT,
        )
        .join(Payment)
        .join(Policy)
        .join(Client)
        .switch(Policy)
        .join(Deal, JOIN.LEFT_OUTER)
        .switch(Payment)
        .join(
            income_subquery,
            JOIN.LEFT_OUTER,
            on=(income_subquery.c.payment_id == Payment.id),
        )
        .switch(Payment)
        .join(
            expense_subquery,
            JOIN.LEFT_OUTER,
            on=(expense_subquery.c.payment_id == Payment.id),
        )
        .group_by(Expense.id, Payment.id, Policy.id, Client.id, Deal.id)
    )
    query = apply_expense_filters(
        query,
        search_text,
        deal_id,
        include_paid,
        expense_date_range=expense_date_range,
        column_filters=column_filters,
    )
    if order_by:
        if isinstance(order_by, str):
            field = getattr(Expense, order_by, Expense.expense_date)
        else:
            field = order_by
        order_expr = field.desc() if order_dir == "desc" else field.asc()
        query = query.order_by(order_expr)
    return query


def get_expenses_by_deal(deal_id: int):
    """Получить расходы, связанные с конкретной сделкой.

    Args:
        deal_id: Идентификатор сделки.

    Returns:
        ModelSelect: Выборка расходов по сделке.
    """
    return (
        Expense.active()
        .select(Expense, Payment, Policy, Client)
        .join(Payment)
        .join(Policy)
        .join(Client)
        .where(Policy.deal_id == deal_id)
        .order_by(Expense.expense_date.asc())
    )
