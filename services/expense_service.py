"""Сервис работы с расходами."""

import logging
from decimal import Decimal

from peewee import Field, JOIN, fn

from database.db import db
from database.models import Client, Deal, Expense, Income, Payment, Policy
from services.payment_service import get_payment_by_id

logger = logging.getLogger(__name__)

INCOME_TOTAL = fn.COALESCE(fn.SUM(Income.amount), 0).alias("income_total")

# ─────────────────────────── CRUD ────────────────────────────


def get_all_expenses():
    """Вернуть все расходы без пометки удаления."""
    return Expense.active()


def get_pending_expenses():
    """Расходы без даты списания."""
    return Expense.active().where(Expense.expense_date.is_null(True))


def get_expense_counts_by_deal_id(deal_id: int) -> tuple[int, int]:
    """Подсчитать количество открытых и закрытых расходов по сделке."""
    base = (
        Expense.active()
        .join(Payment)
        .join(Policy)
        .where(Policy.deal_id == deal_id)
    )
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
    else:
        logger.warning("❗ Расход с id=%s не найден для удаления", expense_id)


def mark_expenses_deleted(expense_ids: list[int]) -> int:
    """Массово пометить расходы удалёнными."""
    if not expense_ids:
        return 0
    return (
        Expense.update(is_deleted=True)
        .where(Expense.id.in_(expense_ids))
        .execute()
    )


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
            return Expense.create(
                payment=payment, policy_id=payment.policy_id, **clean_data
            )
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

    if not updates and not payment_obj:
        return expense

    with db.atomic():
        if payment_obj:
            expense.payment = payment_obj
            expense.policy = payment_obj.policy
        for key, value in updates.items():
            setattr(expense, key, value)
        expense.save()
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
    if search_text:
        query = query.where(
            (Policy.policy_number.contains(search_text))
            | (Client.name.contains(search_text))
        )
    if not include_paid:
        query = query.where(Expense.expense_date.is_null(True))
    if expense_date_range:
        date_from, date_to = expense_date_range
        if date_from:
            query = query.where(Expense.expense_date >= date_from)
        if date_to:
            query = query.where(Expense.expense_date <= date_to)

    from services.query_utils import apply_column_filters, apply_field_filters

    field_filters = {}
    name_filters = {}
    if column_filters:
        for key, val in column_filters.items():
            if key is Income.amount or key is INCOME_TOTAL:
                field_filters[INCOME_TOTAL] = val
            elif isinstance(key, Field):
                field_filters[key] = val
            else:
                name_filters[str(key)] = val

    income_total_filter = field_filters.pop(INCOME_TOTAL, None)
    query = apply_field_filters(query, field_filters)
    query = apply_column_filters(query, name_filters, Expense)

    if income_total_filter:
        query = query.having(
            INCOME_TOTAL.cast("TEXT").contains(income_total_filter)
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
        )
        .join(Payment)
        .join(Policy)
        .join(Client)
        .switch(Policy)
        .join(Deal, JOIN.LEFT_OUTER)
        .switch(Payment)
        .join(Income, JOIN.LEFT_OUTER)
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
