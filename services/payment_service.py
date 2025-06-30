"""Сервис управления платежами."""

import logging
from datetime import date

from peewee import JOIN, ModelSelect  # обязательно
from peewee import fn

from database.models import Client, Expense, Income, Payment, Policy

logger = logging.getLogger(__name__)


# ───────────────────────── базовые CRUD ─────────────────────────


def get_all_payments() -> ModelSelect:
    """Вернуть все платежи без удалённых.

    Returns:
        ModelSelect: Выборка платежей.
    """
    return Payment.select().where(Payment.is_deleted == False)


def get_payments_by_policy_id(policy_id: int) -> ModelSelect:
    """Получить платежи по полису.

    Args:
        policy_id: Идентификатор полиса.

    Returns:
        ModelSelect: Выборка платежей.
    """
    return Payment.select().where(
        (Payment.policy_id == policy_id) & (Payment.is_deleted == False)
    )


def get_payment_by_id(payment_id: int) -> Payment | None:
    """Получить платёж по идентификатору.

    Args:
        payment_id: Идентификатор платежа.

    Returns:
        Payment | None: Найденный платёж или ``None``.
    """
    return Payment.get_or_none(Payment.id == payment_id)


def get_payments_by_client_id(client_id: int) -> ModelSelect:
    """Платежи клиента через связанные полисы.

    Args:
        client_id: Идентификатор клиента.

    Returns:
        ModelSelect: Выборка платежей клиента.
    """
    return (
        Payment.select()
        .join(Policy)
        .where((Policy.client == client_id) & (Payment.is_deleted == False))
    )


def get_payments_page(
    page: int,
    per_page: int,
    search_text: str = "",
    show_deleted: bool = False,
    deal_id: int | None = None,
    only_paid: bool = False,
    **filters,
) -> ModelSelect:
    """Получить страницу платежей по заданным фильтрам.

    Args:
        page: Номер страницы.
        per_page: Количество записей на странице.
        search_text: Строка поиска.
        show_deleted: Учитывать удалённые записи.
        deal_id: Фильтр по сделке.
        only_paid: Только неоплаченные/оплаченные.

    Returns:
        ModelSelect: Отфильтрованная выборка платежей.
    """
    query = build_payment_query(
        search_text=search_text,
        show_deleted=show_deleted,
        deal_id=deal_id,
        only_paid=only_paid,
        **filters,
    )
    offset = (page - 1) * per_page
    return query.order_by(Payment.payment_date.asc()).offset(offset).limit(per_page)


def mark_payment_deleted(payment_id: int):
    """Пометить платёж удалённым."""
    payment = Payment.get_or_none(Payment.id == payment_id)
    if payment:
        payment.is_deleted = True
        payment.save()
    else:
        logger.warning("❗ Платёж с id=%s не найден для удаления", payment_id)


def mark_payments_paid(payment_ids: list[int], paid_date: date | None = None) -> int:
    """Массово отметить платежи как оплаченные.

    Args:
        payment_ids: Список идентификаторов платежей.
        paid_date: Дата фактической оплаты. Если не указана,
            используется ``02.01.1900``.

    Returns:
        int: Количество обновлённых записей.
    """
    if not payment_ids:
        return 0
    paid_date = paid_date or date(1900, 1, 2)
    return (
        Payment.update(actual_payment_date=paid_date)
        .where(Payment.id.in_(payment_ids))
        .execute()
    )


# ─────────────────────────── Добавление ───────────────────────────


def add_payment(**kwargs):
    """Создать платёж и связанные записи дохода и расхода.

    Args:
        **kwargs: Данные платежа, включая ``policy``/``policy_id`` и ``amount``.

    Returns:
        Payment: Созданный платёж.
    """
    from services.income_service import add_income

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

    clean_data = {
        field: kwargs[field]
        for field in allowed_fields
        if field in kwargs  # убрали фильтр по None
    }
    payment = Payment.create(policy=policy, is_deleted=False, **clean_data)
    logger.info(
        "✅ Добавлен платёж #%s к полису #%s на сумму %.2f",
        payment.id,
        policy.policy_number,
        payment.amount,
    )
    try:
        # При создании платежа доход добавляется автоматически, но без суммы.
        # Сумма будет указана отдельно после фактического получения средств.
        add_income(payment=payment, amount=0, policy=policy)
    except Exception as e:
        logger.error("❌ Ошибка при добавлении дохода: %s", e)

    # Автоматическая выплата контрагенту
    from services.expense_service import add_expense

    contractor = (policy.contractor or "").strip()  # строка из полиса
    if contractor:  # есть значение → считаем контрагентом
        try:
            add_expense(
                payment=payment,
                amount=0,
                expense_type="контрагент",
                note=f"выплата контрагенту {contractor}",
            )
            logger.info(
                "💸 Авто-расход контрагенту: платёж #%s ↔ полис #%s (%s)",
                payment.id,
                policy.id,
                contractor,
            )
        except Exception as e:
            logger.error("❌ Ошибка при добавлении расхода: %s", e)

    return payment


# ─────────────────────────── Обновление ───────────────────────────


def update_payment(payment: Payment, **kwargs) -> Payment:
    """Обновить поля платежа.

    Args:
        payment: Объект платежа для обновления.
        **kwargs: Изменяемые поля.

    Returns:
        Payment: Обновлённый платёж.
    """
    allowed_fields = {
        "amount",
        "payment_date",
        "actual_payment_date",
        "policy",
        "policy_id",
    }

    updates = {}

    for key, value in kwargs.items():
        if key in allowed_fields:
            if key == "policy_id" and not kwargs.get("policy"):
                value = Policy.get_or_none(Policy.id == value)
                key = "policy"
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
    only_paid: bool = False,
) -> ModelSelect:
    """Фильтры для выборки платежей."""
    if deal_id is not None:
        query = query.where(Policy.deal_id == deal_id)
    if not show_deleted:
        query = query.where(Payment.is_deleted == False)
    if search_text:
        query = query.where(
            (Policy.policy_number.contains(search_text))
            | (Client.name.contains(search_text))
        )
    if not only_paid:
        query = query.where(Payment.actual_payment_date.is_null(True))

    return query


def build_payment_query(
    search_text: str = "",
    show_deleted: bool = False,
    deal_id: int | None = None,
    only_paid: bool = False,
    **filters,
) -> ModelSelect:
    """Сконструировать базовый запрос платежей с агрегатами."""
    income_subq = Income.select(fn.COUNT(Income.id)).where(Income.payment == Payment.id)
    expense_subq = Expense.select(fn.COUNT(Expense.id)).where(
        Expense.payment == Payment.id
    )

    # Сразу делаем JOIN к Policy и Client
    query = (
        Payment.select(
            Payment,
            Payment.id,
            Payment.amount,
            Payment.payment_date,
            Payment.actual_payment_date,  # 🔧 Явно добавить
            Payment.is_deleted,
            income_subq.alias("income_count"),
            expense_subq.alias("expense_count"),
        )
        .join(Policy)  # обычный JOIN, т.к. все платежи с полисом
        .join(Client, JOIN.LEFT_OUTER, on=(Policy.client == Client.id))
    )

    # Фильтрация по deal_id через Policy
    query = apply_payment_filters(query, search_text, show_deleted, deal_id, only_paid)

    return query


def get_payments_by_deal_id(deal_id: int) -> ModelSelect:
    """Платежи, относящиеся к сделке.

    Args:
        deal_id: Идентификатор сделки.

    Returns:
        ModelSelect: Выборка платежей по сделке.
    """
    return (
        Payment.select()
        .join(Policy)
        .where((Policy.deal_id == deal_id) & (Payment.is_deleted == False))
        .order_by(Payment.payment_date.asc())
    )
