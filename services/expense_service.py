"""Сервис работы с расходами."""

import logging
from decimal import Decimal
from typing import Any

from peewee import Alias, Field, JOIN, fn, Case
from playhouse.shortcuts import Cast

from database.db import db
from database.models import Client, Deal, Expense, Income, Payment, Policy
from services.payment_service import get_payment_by_id
from services.query_utils import (
    _normalize_filter_values,
    apply_search_and_filters,
    sum_column,
)

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

income_total_expr = fn.COALESCE(fn.SUM(income_subquery.c.income_total), 0)
expense_total_expr = fn.COALESCE(fn.SUM(expense_subquery.c.expense_total), 0)
INCOME_TOTAL = income_total_expr.alias("income_total")
OTHER_EXPENSE_TOTAL = (expense_total_expr - Expense.amount).alias("other_expense_total")
net_income_expr = income_total_expr - expense_total_expr
NET_INCOME = net_income_expr.alias("net_income")

# ─────────────────────────── CRUD ────────────────────────────


def get_all_expenses():
    """Вернуть все расходы без пометки удаления."""
    return Expense.active()


def get_pending_expenses():
    """Расходы без даты списания."""
    return Expense.active().where(Expense.expense_date.is_null(True))


def get_expense_counts_by_deal_id(deal_id: int) -> tuple[int, int]:
    """Подсчитать количество открытых и закрытых расходов по сделке."""
    query = (
        Expense.select(
            fn.SUM(
                Case(
                    None,
                    ((Expense.expense_date.is_null(True), 1),),
                    0,
                )
            ).alias("open_count"),
            fn.SUM(
                Case(
                    None,
                    ((Expense.expense_date.is_null(False), 1),),
                    0,
                )
            ).alias("closed_count"),
        )
        .join(Payment)
        .join(Policy)
        .where((Policy.deal_id == deal_id) & (Expense.is_deleted == False))
        .tuples()
        .first()
    )

    if not query:
        return 0, 0

    open_count, closed_count = query
    return int(open_count or 0), int(closed_count or 0)


def get_expense_amounts_by_deal_id(deal_id: int) -> tuple[Decimal, Decimal]:
    """Вернуть суммы запланированных и списанных расходов по сделке."""

    base = (
        Expense.active()
        .join(Payment)
        .join(Policy)
        .where(Policy.deal_id == deal_id)
    )
    planned = sum_column(base.where(Expense.expense_date.is_null(True)), Expense.amount)
    spent = sum_column(base.where(Expense.expense_date.is_null(False)), Expense.amount)
    return planned, spent


def get_expense_count_by_policy(policy_id: int) -> int:
    """Подсчитать количество расходов, связанных с полисом."""
    return (
        Expense.active()
        .where(Expense.policy_id == policy_id)
        .count()
    )


def get_expense_by_id(expense_id: int) -> Expense | None:
    """Получить расход по идентификатору."""
    return Expense.get_or_none(Expense.id == expense_id)


def get_other_expenses(payment_id: int, exclude_id: int) -> list[Expense]:
    """Получить другие расходы по тому же платежу.

    Возвращаются объекты с полями ``expense_type``, ``amount`` и ``expense_date``.
    """
    return list(
        Expense.select(
            Expense.expense_type,
            Expense.amount,
            Expense.expense_date,
        )
        .where((Expense.payment_id == payment_id) & (Expense.id != exclude_id))
        .order_by(Expense.expense_date)
    )


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
        nullable_fields = {"expense_date", "note"}
        for key, value in kwargs.items():
            if key not in allowed_fields:
                continue
            if value == "":
                continue
            if value is None and key not in nullable_fields:
                continue
            if key == "amount" and value is not None:
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
    normalized_order_dir = (order_dir or "").strip().lower()
    if normalized_order_dir not in {"asc", "desc"}:
        normalized_order_dir = "desc"
    logger.debug(
        "get_expenses_page filters=%s order=%s %s",
        column_filters,
        order_by,
        normalized_order_dir,
    )
    query = build_expense_query(
        search_text=search_text,
        show_deleted=show_deleted,
        deal_id=deal_id,
        include_paid=include_paid,
        expense_date_range=expense_date_range,
        column_filters=column_filters,
        order_by=order_by,
        order_dir=normalized_order_dir,
    )
    offset = (page - 1) * per_page
    paged_query = query.limit(per_page).offset(offset)
    filters = {
        "search_text": search_text,
        "show_deleted": show_deleted,
        "deal_id": deal_id,
        "include_paid": include_paid,
        "expense_date_range": expense_date_range,
        "column_filters": column_filters,
    }
    if not paged_query.exists():
        logger.warning("No expenses found for filters=%s", filters)
    return paged_query


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
        Policy.contractor,
        Policy.start_date,
        Policy.note,
    ]

    col_filters = dict(column_filters or {})
    income_total_filter = col_filters.pop(INCOME_TOTAL, None)
    if income_total_filter is None and Income.amount in col_filters:
        income_total_filter = col_filters.pop(Income.amount)
    other_expense_total_filter = col_filters.pop(OTHER_EXPENSE_TOTAL, None)
    net_income_filter = col_filters.pop(NET_INCOME, None)

    query = apply_search_and_filters(
        query, Expense, search_text or "", col_filters, extra_fields
    )

    if not include_paid:
        query = query.where(Expense.expense_date.is_null(True))
    if include_paid and expense_date_range:
        date_from, date_to = expense_date_range
        if date_from:
            query = query.where(Expense.expense_date >= date_from)
        if date_to:
            query = query.where(Expense.expense_date <= date_to)

    def _build_having_condition(expr, value):
        values, include_null = _normalize_filter_values(value)
        if not values and not include_null:
            return None
        condition = None
        for item in values:
            candidate = Cast(expr, "TEXT").contains(item)
            condition = candidate if condition is None else (condition | candidate)
        if include_null:
            null_candidate = expr.is_null(True)
            condition = (
                null_candidate if condition is None else (condition | null_candidate)
            )
        return condition

    for expression, filter_value in (
        (INCOME_TOTAL, income_total_filter),
        (OTHER_EXPENSE_TOTAL, other_expense_total_filter),
        (NET_INCOME, net_income_filter),
    ):
        having_condition = _build_having_condition(expression, filter_value)
        if having_condition is not None:
            query = query.having(having_condition)

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
    normalized_order_dir = (order_dir or "").strip().lower()
    if normalized_order_dir not in {"asc", "desc"}:
        normalized_order_dir = "desc"
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
        .group_by(
            Expense.id,
            Payment.id,
            Policy.id,
            Client.id,
            Deal.id,
        )
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
        field_obj = None
        if isinstance(order_by, str):
            field_obj = getattr(Expense, order_by, None)
            if field_obj is None and "__" in order_by:
                prefix, attr = order_by.split("__", 1)
                related_map = {
                    "payment": Payment,
                    "policy": Policy,
                    "client": Client,
                    "deal": Deal,
                }
                model = related_map.get(prefix)
                if model is not None:
                    field_obj = getattr(model, attr, None)
            if field_obj is None:
                logger.debug(
                    "Unknown order_by='%s', defaulting to expense_date", order_by
                )
                field_obj = Expense.expense_date
        else:
            field_obj = order_by

        if isinstance(field_obj, Alias):
            field_obj = field_obj.unwrap()

        if field_obj is not None and hasattr(field_obj, "asc") and hasattr(field_obj, "desc"):
            order_expr = (
                field_obj.desc()
                if normalized_order_dir == "desc"
                else field_obj.asc()
            )
            query = query.order_by(order_expr)
    logger.debug("expense query SQL: %s", query.sql())
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
