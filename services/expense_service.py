"""Сервис работы с расходами."""

import logging
logger = logging.getLogger(__name__)
from datetime import date

from database.models import Client, Expense, Payment, Policy
from services.payment_service import get_payment_by_id

# ─────────────────────────── CRUD ────────────────────────────

def get_all_expenses():
    """Вернуть все расходы без пометки удаления."""
    return Expense.select().where(Expense.is_deleted == False)


def get_pending_expenses():
    """Расходы без даты списания."""
    return Expense.select().where(
        (Expense.is_deleted == False) &
        (Expense.expense_date.is_null(True))
    )


def get_expense_by_id(expense_id: int) -> Expense | None:
    """Получить расход по идентификатору."""
    return Expense.get_or_none(Expense.id == expense_id)


def mark_expense_deleted(expense_id: int):
    expense = Expense.get_or_none(Expense.id == expense_id)
    if expense:
        expense.is_deleted = True
        expense.save()
    else:
        logger.warning("❗ Расход с id=%s не найден для удаления", expense_id)


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

    try:
        return Expense.create(
            payment=payment,
            policy_id=payment.policy_id,
            is_deleted=False,
            **clean_data
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
    allowed_fields = {"payment", "payment_id", "amount", "expense_type", "expense_date"}

    updates = {}

    for key, value in kwargs.items():
        if key in allowed_fields and value not in ("", None):
            if key == "payment_id" and not kwargs.get("payment"):
                value = get_payment_by_id(value)
                key = "payment"
            updates[key] = value

    if not updates:
        return expense

    for key, value in updates.items():
        setattr(expense, key, value)

    expense.save()
    return expense


# ──────────────────────── Постраничный вывод ───────────────────────



def get_expenses_page(page: int, per_page: int, *, search_text: str = "", show_deleted: bool = False, deal_id: int = None, only_unpaid: bool = False):
    """Вернуть страницу расходов с фильтрами.

    Args:
        page: Номер страницы.
        per_page: Количество записей на странице.
        search_text: Строка поиска по полисам и клиентам.
        show_deleted: Учитывать удалённые записи.
        deal_id: Идентификатор сделки для фильтра.
        only_unpaid: Показывать только неоплаченные расходы.

    Returns:
        ModelSelect: Выборка расходов.
    """
    query = build_expense_query(search_text=search_text, show_deleted=show_deleted, deal_id=deal_id, only_unpaid=only_unpaid)
    offset = (page - 1) * per_page
    return query.order_by(Expense.expense_date.desc()).limit(per_page).offset(offset)


def apply_expense_filters(query, search_text=None, show_deleted=False, deal_id=None, only_unpaid=False, **kwargs):



    if not show_deleted:
        query = query.where(Expense.is_deleted == False)
    if deal_id:
        query = query.where(Policy.deal_id == deal_id)
    if search_text:
        query = query.where(
            (Policy.policy_number.contains(search_text)) |
            (Client.name.contains(search_text))
        )
    if only_unpaid:
        query = query.where(Expense.expense_date.is_null(True))

    return query



def build_expense_query(search_text=None, show_deleted=False, deal_id=None, only_unpaid=False, **kwargs):

    query = Expense.select(Expense, Payment, Policy, Client).join(Payment).join(Policy).join(Client)
    return apply_expense_filters(query, search_text, show_deleted, deal_id, only_unpaid, **kwargs)



def get_expenses_by_deal(deal_id: int):
    """Получить расходы, связанные с конкретной сделкой.

    Args:
        deal_id: Идентификатор сделки.

    Returns:
        ModelSelect: Выборка расходов по сделке.
    """
    return (
        Expense
        .select(Expense, Payment, Policy, Client)
        .join(Payment)
        .join(Policy)
        .join(Client)
        .where(
            (Policy.deal_id == deal_id) &
            (Expense.is_deleted == False)
        )
        .order_by(Expense.expense_date.asc())
    )
