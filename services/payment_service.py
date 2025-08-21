"""Сервис управления платежами."""

import logging
from datetime import date
from decimal import Decimal

from peewee import JOIN, ModelSelect, fn

from database.db import db
from database.models import Client, Expense, Income, Payment, Policy

ACTIVE = Payment.is_deleted == False

logger = logging.getLogger(__name__)


# ───────────────────────── базовые CRUD ─────────────────────────


def get_all_payments() -> ModelSelect:
    """Вернуть все платежи без удалённых."""
    return Payment.select().where(ACTIVE)


def get_payments_by_policy_id(policy_id: int) -> ModelSelect:
    """Получить платежи по полису."""
    return Payment.select().where((Payment.policy_id == policy_id) & ACTIVE)


def get_payment_by_id(payment_id: int) -> Payment | None:
    """Получить платёж по идентификатору."""
    return Payment.get_or_none(Payment.id == payment_id)


def get_payments_by_client_id(client_id: int) -> ModelSelect:
    """Платежи клиента через связанные полисы."""
    return (
        Payment.select()
        .join(Policy)
        .where((Policy.client == client_id) & ACTIVE)
    )


def get_payments_page(
    page: int,
    per_page: int,
    search_text: str = "",
    show_deleted: bool = False,
    deal_id: int | None = None,
    include_paid: bool = True,
    column_filters: dict[str, str] | None = None,
    **filters,
) -> ModelSelect:
    """Получить страницу платежей по заданным фильтрам."""
    query = build_payment_query(
        search_text=search_text,
        show_deleted=show_deleted,
        deal_id=deal_id,
        include_paid=include_paid,
        column_filters=column_filters,
        **filters,
    )
    offset = (page - 1) * per_page
    return query.order_by(Payment.payment_date.asc()).offset(offset).limit(per_page)


def mark_payment_deleted(payment_id: int):
    """Пометить платёж удалённым."""
    payment = Payment.get_or_none(Payment.id == payment_id)
    if payment:
        payment.soft_delete()
    else:
        logger.warning("❗ Платёж с id=%s не найден для удаления", payment_id)


def mark_payments_paid(payment_ids: list[int], paid_date: date | None = None) -> int:
    """
    Массово отметить платежи как оплаченные.

    Если дата не указана, используется текущая. Обновляются только платежи,
    у которых ещё нет фактической даты оплаты.
    """
    if not payment_ids:
        return 0
    paid_date = paid_date or date.today()
    return (
        Payment.update(actual_payment_date=paid_date)
        .where(
            (Payment.id.in_(payment_ids))
            & Payment.actual_payment_date.is_null(True)
        )
        .execute()
    )


# ─────────────────────────── Добавление ───────────────────────────


def add_payment(**kwargs):
    """Создать платёж и связанные записи дохода и расхода."""
    from services.income_service import add_income
    from services.expense_service import add_expense

    policy = kwargs.get("policy") or Policy.get_or_none(
        Policy.id == kwargs.get("policy_id")
    )
    if not policy:
        logger.warning(
            "❌ Не удалось добавить платёж: не найден полис #%s",
            kwargs.get("policy_id"),
        )
        raise ValueError("Полис не найден")

    amount = kwargs.get("amount")
    payment_date = kwargs.get("payment_date")
    if amount is None or payment_date is None:
        raise ValueError("Обязательные поля: amount и payment_date")

    allowed_fields = {"amount", "payment_date", "actual_payment_date"}
    clean_data = {f: kwargs[f] for f in allowed_fields if f in kwargs}
    if "amount" in clean_data:
        clean_data["amount"] = Decimal(str(clean_data["amount"]))

    contractor = (policy.contractor or "").strip()

    try:
        with db.atomic():
            payment = Payment.create(policy=policy, is_deleted=False, **clean_data)
            logger.info(
                "✅ Добавлен платёж #%s к полису #%s на сумму %.2f",
                payment.id,
                policy.policy_number,
                payment.amount,
            )

            # Доход добавляется автоматически, но с нулевой суммой
            add_income(payment=payment, amount=Decimal("0"), policy=policy)

            # Авто-расход контрагенту (если указан в полисе)
            if contractor:
                add_expense(
                    payment=payment,
                    amount=Decimal("0"),
                    expense_type="контрагент",
                    note=f"выплата контрагенту {contractor}",
                )
                logger.info(
                    "💸 Авто-расход контрагенту: платёж #%s ↔ полис #%s (%s)",
                    payment.id,
                    policy.id,
                    contractor,
                )

        return payment
    except Exception:
        logger.exception("❌ Ошибка при добавлении платежа")
        raise


def sync_policy_payments(policy: Policy, payments: list[dict] | None) -> None:
    """Синхронизировать платежи полиса с переданным списком."""
    if payments is None:
        return

    # Удаляем нулевые при наличии ненулевых
    zero_payments = [
        p for p in payments if Decimal(str(p.get("amount", 0))) == Decimal("0")
    ]
    if zero_payments and any(
        Decimal(str(p.get("amount", 0))) != Decimal("0") for p in payments
    ):
        (
            Payment.update(is_deleted=True)
            .where(
                (Payment.policy == policy)
                & (Payment.amount == Decimal("0"))
                & ACTIVE
            )
            .execute()
        )
        payments = [
            p for p in payments if Decimal(str(p.get("amount", 0))) != Decimal("0")
        ]

    existing = {
        (p.payment_date, p.amount): p
        for p in policy.payments.where(ACTIVE)
    }
    incoming: set[tuple[date, Decimal]] = set()

    for data in payments:
        payment_date = data.get("payment_date")
        amount = data.get("amount")
        if payment_date is None or amount is None:
            continue
        amount = Decimal(str(amount))
        key = (payment_date, amount)
        incoming.add(key)
        if key not in existing:
            add_payment(
                policy=policy, payment_date=payment_date, amount=amount
            )

    for key, payment in existing.items():
        if key not in incoming:
            if hasattr(payment, "soft_delete"):
                payment.soft_delete()
            else:
                payment.delete_instance()


# ─────────────────────────── Обновление ───────────────────────────


def update_payment(payment: Payment, **kwargs) -> Payment:
    """Обновить поля платежа."""
    allowed_fields = {
        "amount",
        "payment_date",
        "actual_payment_date",
        "policy",
        "policy_id",
    }
    updates: dict = {}

    for key, value in kwargs.items():
        if key in allowed_fields:
            if key == "policy_id" and not kwargs.get("policy"):
                value = Policy.get_or_none(Policy.id == value)
                key = "policy"
            if key == "amount" and value is not None:
                value = Decimal(str(value))
            updates[key] = value

    if not updates:
        return payment

    for key, value in updates.items():
        setattr(payment, key, value)

    payment.save()
    return payment


def apply_payment_filters(
    query: ModelSelect,
    search_text: str = "",
    show_deleted: bool = False,
    deal_id: int | None = None,
    include_paid: bool = True,
    column_filters: dict[str, str] | None = None,
) -> ModelSelect:
    """Фильтры для выборки платежей."""
    if deal_id is not None:
        query = query.where(Policy.deal_id == deal_id)
    if not show_deleted:
        query = query.where(ACTIVE)
    if search_text:
        query = query.where(
            (Policy.policy_number.contains(search_text))
            | (Client.name.contains(search_text))
        )
    if not include_paid:
        query = query.where(Payment.actual_payment_date.is_null(True))

    from services.query_utils import apply_column_filters
    query = apply_column_filters(query, column_filters, Payment)
    return query


def build_payment_query(
    search_text: str = "",
    show_deleted: bool = False,
    deal_id: int | None = None,
    include_paid: bool = True,
    column_filters: dict[str, str] | None = None,
    **filters,
) -> ModelSelect:
    """Сконструировать базовый запрос платежей с агрегатами."""
    income_subq = Income.select(fn.COUNT(Income.id)).where(Income.payment == Payment.id)
    expense_subq = Expense.select(fn.COUNT(Expense.id)).where(
        Expense.payment == Payment.id
    )

    query = (
        Payment.select(
            Payment,
            Payment.id,
            Payment.amount,
            Payment.payment_date,
            Payment.actual_payment_date,
            Payment.is_deleted,
            income_subq.alias("income_count"),
            expense_subq.alias("expense_count"),
        )
        .join(Policy)
        .join(Client, JOIN.LEFT_OUTER, on=(Policy.client == Client.id))
    )

    query = apply_payment_filters(
        query, search_text, show_deleted, deal_id, include_paid, column_filters
    )
    return query


def get_payments_by_deal_id(deal_id: int) -> ModelSelect:
    """Платежи, относящиеся к сделке."""
    return (
        Payment.select()
        .join(Policy)
        .where((Policy.deal_id == deal_id) & ACTIVE)
        .order_by(Payment.payment_date.asc())
    )
