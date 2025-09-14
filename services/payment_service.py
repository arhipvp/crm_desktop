"""Сервис управления платежами."""

import logging
from collections import defaultdict
from datetime import date
from decimal import Decimal

from peewee import JOIN, ModelSelect, fn, Field

from database.db import db
from database.models import Client, Expense, Income, Payment, Policy
from services.query_utils import apply_search_and_filters

# Выражение для активных платежей (не удалённых)
ACTIVE = (Payment.is_deleted == False)

logger = logging.getLogger(__name__)


# ───────────────────────── базовые CRUD ─────────────────────────


def get_all_payments() -> ModelSelect:
    """Вернуть все платежи без удалённых."""
    return Payment.active()


def get_payments_by_policy_id(policy_id: int) -> ModelSelect:
    """Получить платежи по полису."""
    return Payment.active().where(Payment.policy_id == policy_id)


def get_payment_by_id(payment_id: int) -> Payment | None:
    """Получить платёж по идентификатору."""
    return Payment.get_or_none(Payment.id == payment_id)


def get_payments_by_client_id(client_id: int) -> ModelSelect:
    """Платежи клиента через связанные полисы."""
    return (
        Payment.active()
        .join(Policy)
        .where(Policy.client == client_id)
    )


def get_payments_page(
    page: int,
    per_page: int,
    search_text: str = "",
    show_deleted: bool = False,
    deal_id: int | None = None,
    include_paid: bool = True,
    column_filters: dict | None = None,
    order_by: str | Field = Payment.payment_date,
    order_dir: str = "asc",
    **filters,
) -> ModelSelect:
    """Получить страницу платежей по заданным фильтрам."""
    query = build_payment_query(
        search_text=search_text,
        show_deleted=show_deleted,
        deal_id=deal_id,
        include_paid=include_paid,
        column_filters=column_filters,
        order_by=order_by,
        order_dir=order_dir,
        **filters,
    )
    if isinstance(order_by, str):
        order_field = getattr(Payment, order_by, Payment.payment_date)
    else:
        order_field = order_by
    order_expr = (
        order_field.desc() if order_dir == "desc" else order_field.asc()
    )
    offset = (page - 1) * per_page
    return query.order_by(order_expr).offset(offset).limit(per_page)


def mark_payment_deleted(payment_id: int):
    """Пометить платёж удалённым."""
    payment = Payment.get_or_none(Payment.id == payment_id)
    if not payment:
        logger.warning("❗ Платёж с id=%s не найден для удаления", payment_id)
        return

    with db.atomic():
        income_deleted = (
            Income.update(is_deleted=True)
            .where(Income.payment == payment)
            .execute()
        )
        expense_deleted = (
            Expense.update(is_deleted=True)
            .where(Expense.payment == payment)
            .execute()
        )
        payment.soft_delete()

    logger.info(
        "🗑️ Помечен удалённым платёж #%s; доходов=%s, расходов=%s",
        payment_id,
        income_deleted,
        expense_deleted,
    )


def restore_payment(payment_id: int):
    """Снять пометку удаления с платежа и связанных записей."""
    payment = Payment.get_or_none(Payment.id == payment_id)
    if not payment:
        logger.warning(
            "❗ Платёж с id=%s не найден для восстановления", payment_id
        )
        return

    with db.atomic():
        income_restored = (
            Income.update(is_deleted=False)
            .where(Income.payment == payment)
            .execute()
        )
        expense_restored = (
            Expense.update(is_deleted=False)
            .where(Expense.payment == payment)
            .execute()
        )
        payment.is_deleted = False
        payment.save(only=[Payment.is_deleted])

    logger.info(
        "♻️ Восстановлен платёж #%s; доходов=%s, расходов=%s",
        payment_id,
        income_restored,
        expense_restored,
    )


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
    if contractor in {"", "-", "—"}:
        contractor = ""

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
        subq = (
            Payment.active()
            .where((Payment.policy == policy) & (Payment.amount == Decimal("0")))
            .select(Payment.id)
        )
        (
            Payment.update(is_deleted=True)
            .where(Payment.id.in_(subq))
            .execute()
        )
        payments = [
            p for p in payments if Decimal(str(p.get("amount", 0))) != Decimal("0")
        ]

    existing: defaultdict[tuple[date, Decimal], list[Payment]] = defaultdict(list)
    for p in Payment.active().where(Payment.policy == policy):
        existing[(p.payment_date, p.amount)].append(p)

    for data in payments:
        payment_date = data.get("payment_date")
        amount = data.get("amount")
        actual_payment_date = data.get("actual_payment_date")
        if payment_date is None or amount is None:
            continue
        amount = Decimal(str(amount))
        key = (payment_date, amount)
        if existing[key]:
            payment = existing[key].pop(0)
            if (
                actual_payment_date is not None
                and payment.actual_payment_date != actual_payment_date
            ):
                update_payment(payment, actual_payment_date=actual_payment_date)
        else:
            add_payment(
                policy=policy,
                payment_date=payment_date,
                amount=amount,
                actual_payment_date=actual_payment_date,
            )

    for payments_list in existing.values():
        for payment in payments_list:
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
    deal_id: int | None = None,
    include_paid: bool = True,
    column_filters: dict | None = None,
) -> ModelSelect:
    """Фильтры для выборки платежей."""
    if deal_id is not None:
        query = query.where(Policy.deal_id == deal_id)
    extra_fields = [Policy.policy_number, Client.name]
    query = apply_search_and_filters(
        query, Payment, search_text, column_filters, extra_fields
    )
    if not include_paid:
        query = query.where(Payment.actual_payment_date.is_null(True))
    return query


def build_payment_query(
    search_text: str = "",
    show_deleted: bool = False,
    deal_id: int | None = None,
    include_paid: bool = True,
    column_filters: dict | None = None,
    order_by: str | Field | None = None,
    order_dir: str = "asc",
    **filters,
) -> ModelSelect:
    """Сконструировать базовый запрос платежей с агрегатами."""
    income_subq = Income.select(fn.COUNT(Income.id)).where(Income.payment == Payment.id)
    expense_subq = Expense.select(fn.COUNT(Expense.id)).where(
        Expense.payment == Payment.id
    )

    base = Payment.active() if not show_deleted else Payment.select()
    query = (
        base.select(
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
        query, search_text=search_text, deal_id=deal_id, include_paid=include_paid, column_filters=column_filters
    )
    return query


def get_payments_by_deal_id(deal_id: int) -> ModelSelect:
    """Платежи, относящиеся к сделке."""
    return (
        Payment.active()
        .join(Policy)
        .where(Policy.deal_id == deal_id)
        .order_by(Payment.payment_date.asc())
    )


def get_payment_counts_by_deal_id(deal_id: int) -> tuple[int, int]:
    """Подсчитать количество открытых и закрытых платежей по сделке."""
    base = Payment.active().join(Policy).where(Policy.deal_id == deal_id)
    open_count = base.where(Payment.actual_payment_date.is_null(True)).count()
    closed_count = base.where(Payment.actual_payment_date.is_null(False)).count()
    return open_count, closed_count
