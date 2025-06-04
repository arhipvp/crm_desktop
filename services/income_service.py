
import logging

logger = logging.getLogger(__name__)
from datetime import date

from database.models import Client, Income, Payment, Policy
from services.payment_service import get_payment_by_id
from services.task_service import add_task

# ───────────────────────── базовые CRUD ─────────────────────────

def get_all_incomes():
    return Income.select().where(Income.is_deleted == False)


def get_pending_incomes():
    return Income.select().where(
        (Income.is_deleted == False) &
        (Income.received_date.is_null(True))
    )


def get_income_by_id(income_id: int):
    return Income.get_or_none(Income.id == income_id)


def mark_income_deleted(income_id: int):
    income = Income.get_or_none(Income.id == income_id)
    if income:
        income.is_deleted = True
        income.save()
    else:
        logger.warning("❗ Доход с id=%s не найден для удаления", income_id)


def get_incomes_page(
    page: int, per_page: int,
    order_by: str = "received_date",
    order_dir: str = "desc",
    search_text: str = "",
    show_deleted: bool = False,
    only_unreceived: bool = False,
    received_date_range=None,
    **kwargs
):
    query = build_income_query(
        search_text=search_text,
        show_deleted=show_deleted,
        only_unreceived=only_unreceived,
        received_date_range=received_date_range,
        **kwargs
    )
    # --- сортировка ---
    # --- сортировка ---
    if hasattr(Income, order_by):
        field = getattr(Income, order_by)
        query = query.order_by(field.desc() if order_dir == "desc" else field.asc())
    else:
        query = query.order_by(Income.received_date.desc())

    offset = (page - 1) * per_page
    return query.limit(per_page).offset(offset)





# ─────────────────────────── Добавление ───────────────────────────

def add_income(**kwargs):
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

    try:
        income = Income.create(
            payment=payment,
            is_deleted=False,
            **clean_data
        )
    except Exception as e:
        logger.error("❌ Ошибка при создании дохода: %s", e)
        raise


    # Автоматическая задача
    # due_date = payment.payment_date or date.today()
    # add_task(
    #     title="получить",
    #     due_date=due_date,
    #     policy_id=payment.policy_id
    # )

    return income


# ─────────────────────────── Обновление ───────────────────────────

def update_income(income: Income, **kwargs):
    allowed_fields = {"payment", "payment_id", "amount", "received_date", "commission_source"}

    updates = {}

    for key in allowed_fields:
        if key in kwargs:
            value = kwargs[key]
            if key == "payment_id" and not kwargs.get("payment"):
                value = get_payment_by_id(value)
                key = "payment"
            updates[key] = value

    if not updates:
        return income

    for key, value in updates.items():
        setattr(income, key, value)
    logger.debug("💬 update_income: received_date=%r", updates.get("received_date"))
    logger.debug("💬 final obj: income.received_date = %r", income.received_date)

    income.save()
    return income


def apply_income_filters(query, search_text="", show_deleted=False, only_unreceived=False, received_date_range=None, deal_id=None):
    if not show_deleted:
        query = query.where(Income.is_deleted == False)
    if search_text:
        query = query.where(
            (Policy.policy_number.contains(search_text)) |
            (Client.name.contains(search_text))
        )
    if only_unreceived:
        query = query.where(Income.received_date.is_null(True))
    if received_date_range:
        date_from, date_to = received_date_range
        if date_from:
            query = query.where(Income.received_date >= date_from)
        if date_to:
            query = query.where(Income.received_date <= date_to)
    if deal_id:
        query = query.where(Policy.deal_id == deal_id)
    return query


def build_income_query(
    search_text: str = "",
    show_deleted: bool = False,
    only_unreceived: bool = False,
    received_date_range=None,
    **kwargs
):
    # JOIN Payment, Policy, Client
    query = (
        Income
        .select(
            Income,
            Payment,
            Policy,
            Client
        )
        .join(Payment, on=(Income.payment == Payment.id))
        .switch(Payment)
        .join(Policy, on=(Payment.policy == Policy.id))
        .switch(Policy)
        .join(Client, on=(Policy.client == Client.id))
    )

    if not show_deleted:
        query = query.where(Income.is_deleted == False)

    if search_text:
        query = query.where(
            (Policy.policy_number.contains(search_text)) |
            (Client.name.contains(search_text))
        )
        
    if only_unreceived:
        query = query.where(Income.received_date.is_null(True))
    if received_date_range:
        date_from, date_to = received_date_range
        if date_from:
            query = query.where(Income.received_date >= date_from)
        if date_to:
            query = query.where(Income.received_date <= date_to)
    deal_id = kwargs.get("deal_id")
    if deal_id:
        query = query.where(Policy.deal_id == deal_id)

    return query


def create_stub_income(deal_id: int | None = None) -> Income:
    from services.payment_service import get_all_payments
    payments = get_all_payments()
    if deal_id:
        payments = [p for p in payments if p.policy and p.policy.deal_id == deal_id]
    if not payments:
        raise ValueError("Нет доступных платежей")
    return Income(payment=payments[0])
