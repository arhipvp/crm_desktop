"""Сервис управления страховыми полисами."""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Iterable

from peewee import JOIN, Field, fn, Case

from core.app_context import get_app_context
from database.db import db

from database.models import Client, Deal, Expense, Payment, Policy
from infrastructure.drive_gateway import DriveGateway
from services import executor_service as es
from services.clients import get_client_by_id
from services.deal_service import get_deal_by_id
from services.folder_utils import create_policy_folder, is_drive_link, open_folder
from services.payment_service import (
    add_payment,
    sync_policy_payments,
)
from services.telegram_service import notify_executor
from services.validators import normalize_policy_number
from services.query_utils import apply_search_and_filters



logger = logging.getLogger(__name__)


def _resolve_gateway(gateway: DriveGateway | None) -> DriveGateway:
    return gateway or get_app_context().drive_gateway

# ─────────────────────────── Исключения ───────────────────────────


class DuplicatePolicyError(ValueError):
    """Ошибка, возникающая при попытке создать полис с существующим номером."""

    def __init__(self, existing_policy: Policy, diff_fields: list[str]):
        msg = "Такой полис уже найден."
        if diff_fields:
            msg += " Отличаются поля: " + ", ".join(diff_fields)
        else:
            msg += " Все данные совпадают."
        super().__init__(msg)
        self.existing_policy = existing_policy
        self.diff_fields = diff_fields

# ───────────────────────── базовые CRUD ─────────────────────────


def get_all_policies():
    """Вернуть все полисы без удалённых.

    Returns:
        ModelSelect: Выборка полисов.
    """

    return (
        Policy.select(Policy, Client)
        .join(Client)
        .where(Policy.is_deleted == False)
    )


def get_policies_by_client_id(client_id: int):
    """Полисы, принадлежащие клиенту.

    Args:
        client_id: Идентификатор клиента.

    Returns:
        ModelSelect: Выборка полисов клиента.
    """
    return Policy.active().where(Policy.client_id == client_id)


def get_policies_by_deal_id(deal_id: int):
    """Полисы, связанные со сделкой.

    Args:
        deal_id: Идентификатор сделки.

    Returns:
        ModelSelect: Выборка полисов.
    """
    return (
        Policy.active()
        .where(Policy.deal_id == deal_id)
        .order_by(Policy.start_date.asc())
    )


def get_policy_counts_by_deal_id(deal_id: int) -> tuple[int, int]:
    """Подсчитать количество открытых и закрытых полисов по сделке."""
    today = date.today()
    query = (
        Policy.select(
            fn.SUM(
                Case(
                    None,
                    (
                        (
                            (Policy.end_date.is_null(True))
                            | (Policy.end_date >= today),
                            1,
                        ),
                    ),
                    0,
                )
            ).alias("open_count"),
            fn.SUM(
                Case(
                    None,
                    (
                        (
                            (Policy.end_date.is_null(False))
                            & (Policy.end_date < today),
                            1,
                        ),
                    ),
                    0,
                )
            ).alias("closed_count"),
        )
        .where((Policy.deal_id == deal_id) & (Policy.is_deleted == False))
        .tuples()
        .first()
    )

    if not query:
        return 0, 0

    open_count, closed_count = query
    return int(open_count or 0), int(closed_count or 0)


def get_policy_by_number(policy_number: str):
    """Найти полис по его номеру.

    Args:
        policy_number: Номер полиса.

    Returns:
        Policy | None: Найденный полис либо ``None``.
    """
    return Policy.get_or_none(Policy.policy_number == policy_number)


def _check_duplicate_policy(
    policy_number: str,
    client_id: int,
    deal_id: int | None,
    data: dict,
    *,
    exclude_id: int | None = None,
) -> None:
    """Проверить наличие дубликата и, если найден, поднять ``ValueError``.

    Сравниваются ключевые поля полиса среди **не удалённых** записей. Если все
    совпадают — сообщение сообщает об идентичности, иначе перечисляются
    отличающиеся поля. Полисы, помеченные как удалённые, игнорируются.
    """

    if not policy_number:
        return

    policy_number = normalize_policy_number(policy_number)
    query = Policy.active().where(Policy.policy_number == policy_number)
    if exclude_id is not None:
        query = query.where(Policy.id != exclude_id)

    existing = query.get_or_none()
    if not existing:
        return

    fields_to_compare = {
        "client_id": client_id,
        "deal_id": deal_id,
        **data,
    }

    diffs = [
        fname for fname, val in fields_to_compare.items()
        if getattr(existing, fname) != val
    ]

    raise DuplicatePolicyError(existing, diffs)


def _get_first_payment_date(
    payments: Iterable[dict], *, fallback: date | None = None
) -> date | None:
    first_date: date | None = None
    for payment in payments:
        if not isinstance(payment, dict):
            continue
        payment_date = payment.get("payment_date") or fallback
        if payment_date is None:
            continue
        if first_date is None or payment_date < first_date:
            first_date = payment_date
    return first_date


@dataclass(slots=True)
class ContractorExpenseResult:
    """Результат создания расходов для контрагента."""

    created: list[Expense]
    updated: list[Expense]

    def has_changes(self) -> bool:
        return bool(self.created or self.updated)


def get_policies_page(
    page,
    per_page,
    search_text="",
    show_deleted=False,
    deal_id=None,
    client_id=None,
    order_by: str | Field | None = Policy.start_date,
    order_dir="asc",
    include_renewed=True,
    without_deal_only=False,
    column_filters: dict | None = None,
    **filters,
):
    """Получить страницу полисов с указанными фильтрами.

    Args:
        page: Номер страницы.
        per_page: Количество записей на странице.
        search_text: Поисковая строка.
        show_deleted: Учитывать удалённые записи.
        deal_id: Фильтр по сделке.
        client_id: Фильтр по клиенту.
        order_by: Поле сортировки.
        order_dir: Направление сортировки.
        include_renewed: Показывать продлённые полисы.
        without_deal_only: Только полисы без сделки.
        column_filters: Фильтры по столбцам.

    Returns:
        ModelSelect: Отфильтрованная выборка полисов.
    """
    if isinstance(order_by, Field):
        order_field = order_by
    elif isinstance(order_by, str):
        candidate = getattr(Policy, order_by, None)
        order_field = candidate if isinstance(candidate, Field) else Policy.start_date
    else:
        order_field = Policy.start_date

    normalized_order_dir = (order_dir or "").strip().lower()
    if normalized_order_dir not in {"asc", "desc"}:
        normalized_order_dir = "asc"
    query = build_policy_query(
        search_text=search_text,
        show_deleted=show_deleted,
        deal_id=deal_id,
        client_id=client_id,
        include_renewed=include_renewed,
        without_deal_only=without_deal_only,
        column_filters=column_filters,
        order_by=order_field,
        **filters,
    )
    if normalized_order_dir == "desc":
        query = query.order_by(order_field.desc())
    else:
        query = query.order_by(order_field.asc())
    offset = (page - 1) * per_page
    return query.offset(offset).limit(per_page)


def mark_policy_deleted(
    policy_id: int, *, gateway: DriveGateway | None = None
) -> None:
    policy = Policy.get_or_none(Policy.id == policy_id)
    if policy:
        policy.soft_delete()
        try:
            from services.folder_utils import rename_policy_folder

            new_number = f"{policy.policy_number} deleted"
            resolved_gateway = _resolve_gateway(gateway)
            new_path, new_link = rename_policy_folder(
                policy.client.name,
                policy.policy_number,
                policy.deal.description if policy.deal_id else None,
                policy.client.name,
                new_number,
                policy.deal.description if policy.deal_id else None,
                policy.drive_folder_link
                if is_drive_link(policy.drive_folder_link)
                else None,
                gateway=resolved_gateway,
            )
            policy.policy_number = new_number
            fields_to_update = [Policy.policy_number, Policy.is_deleted]
            if new_path and new_path != policy.drive_folder_path:
                policy.drive_folder_path = new_path
                fields_to_update.append(Policy.drive_folder_path)
            if new_link and new_link != policy.drive_folder_link:
                policy.drive_folder_link = new_link
                fields_to_update.append(Policy.drive_folder_link)
            policy.save(only=fields_to_update)
            logger.info(
                "Полис id=%s №%s помечен удалённым",
                policy.id,
                policy.policy_number,
            )
        except Exception:
            logger.exception(
                "Не удалось пометить папку полиса id=%s №%s удалённой",
                policy.id,
                policy.policy_number,
            )
    else:
        logger.warning("❗ Полис id=%s не найден для удаления", policy_id)


def mark_policies_deleted(
    policy_ids: list[int], *, gateway: DriveGateway | None = None
) -> int:
    """Массово помечает полисы удалёнными."""
    if not policy_ids:
        return 0

    count = 0
    resolved_gateway = _resolve_gateway(gateway) if policy_ids else None
    for pid in policy_ids:
        before = Policy.get_or_none(Policy.id == pid)
        if before and not before.is_deleted:
            mark_policy_deleted(pid, gateway=resolved_gateway)
            count += 1
    logger.info("Полисов помечено удалёнными: %s", count)
    return count


# Уведомления
def _notify_policy_added(policy: Policy) -> None:
    """Уведомить исполнителя сделки о добавленном полисе."""
    if not policy.deal_id:
        return
    ex = es.get_executor_for_deal(policy.deal_id)
    if not ex or not es.is_approved(ex.tg_id):
        return
    deal = get_deal_by_id(policy.deal_id)
    if not deal:
        return
    desc = f" — {deal.description}" if deal.description else ""
    text = (
        f"📄 В вашу сделку #{deal.id}{desc} добавлен полис id={policy.id} №{policy.policy_number}"
    )
    notify_executor(ex.tg_id, text)


def add_contractor_expense(
    policy: Policy, payments: Iterable[Payment] | None = None
) -> ContractorExpenseResult:
    """Создать или обновить расходы "контрагент" для выбранных платежей."""

    from services.expense_service import add_expense

    contractor = (policy.contractor or "").strip()
    if contractor in {"", "-", "—"}:
        raise ValueError("У полиса отсутствует контрагент")

    if payments is None:
        payment_objects = list(
            Payment.active()
            .where(Payment.policy == policy)
            .order_by(Payment.payment_date)
        )
        if not payment_objects:
            raise ValueError("У полиса отсутствуют платежи")
    else:
        payment_objects: list[Payment] = []
        for payment in payments:
            if isinstance(payment, Payment):
                payment_obj = payment
            elif hasattr(payment, "id"):
                payment_id = getattr(payment, "id")
                payment_obj = (
                    Payment.active()
                    .where((Payment.id == payment_id) & (Payment.policy == policy))
                    .get_or_none()
                )
            else:
                payment_obj = (
                    Payment.active()
                    .where((Payment.id == payment) & (Payment.policy == policy))
                    .get_or_none()
                )

            if payment_obj is None or payment_obj.policy_id != policy.id:
                raise ValueError("Платёж не найден или не принадлежит полису")

            payment_objects.append(payment_obj)

        if not payment_objects:
            return ContractorExpenseResult(created=[], updated=[])

        unique: dict[int, Payment] = {}
        for payment_obj in payment_objects:
            unique[payment_obj.id] = payment_obj
        payment_objects = sorted(
            unique.values(), key=lambda p: p.payment_date or date.min
        )

    payment_ids = [p.id for p in payment_objects]
    expenses_map: dict[int, list[Expense]] = {pid: [] for pid in payment_ids}

    if payment_ids:
        expenses_query = (
            Expense.active()
            .where(
                (Expense.payment_id.in_(payment_ids))
                & (Expense.expense_type == "контрагент")
            )
        )
        for expense in expenses_query:
            expenses_map.setdefault(expense.payment_id, []).append(expense)

    created_expenses: list[Expense] = []
    updated_expenses: list[Expense] = []
    note_template = f"выплата контрагенту {contractor}"

    with db.atomic():
        for payment in payment_objects:
            expenses = expenses_map.get(payment.id, [])
            if not expenses:
                expense_kwargs = dict(
                    payment=payment,
                    amount=Decimal("0"),
                    expense_type="контрагент",
                    note=note_template,
                )

                created_expenses.append(add_expense(**expense_kwargs))
                continue

            for expense in expenses:
                changed = False
                if expense.note != note_template:
                    expense.note = note_template
                    changed = True
                if changed:
                    expense.save(only=[Expense.note])
                    updated_expenses.append(expense)

    return ContractorExpenseResult(created=created_expenses, updated=updated_expenses)


# ─────────────────────────── Добавление ───────────────────────────


def add_policy(
    *,
    payments=None,
    first_payment_paid=False,
    gateway: DriveGateway | None = None,
    **kwargs,
):
    """Создаёт новый полис с привязкой к клиенту и (опционально) сделке.

    Аргумент ``payments`` передаётся только при необходимости: когда он
    отсутствует или пуст, сервис сам добавляет авто-нулевой платёж на дату
    начала полиса, чтобы сохранить ожидаемую структуру платежей.
    """
    # ────────── Клиент ──────────
    client = kwargs.get("client") or get_client_by_id(kwargs.get("client_id"))
    if not client:
        logger.warning("❌ add_policy: не найден client_id=%s", kwargs.get("client_id"))
        raise ValueError("client_id обязателен и должен существовать")

    # ────────── Сделка ──────────
    deal = kwargs.get("deal")
    if not deal and kwargs.get("deal_id"):
        deal = get_deal_by_id(kwargs["deal_id"])

    # ────────── Очистка данных ──────────
    allowed_fields = {
        "policy_number",
        "insurance_type",
        "insurance_company",
        "contractor",
        "sales_channel",
        "start_date",
        "end_date",
        "vehicle_brand",
        "vehicle_model",
        "vehicle_vin",
        "note",
    }

    clean_data: dict[str, Any] = {}
    for field in allowed_fields:
        if field not in kwargs:
            continue
        val = kwargs[field]
        if isinstance(val, str):
            val = val.strip()
            if val in {"", "-", "—"}:
                continue
        elif val in ("", None):
            continue
        clean_data[field] = val

    # Обязателен номер полиса
    if not clean_data.get("policy_number"):
        raise ValueError("Поле 'policy_number' обязательно для заполнения.")
    clean_data["policy_number"] = normalize_policy_number(clean_data["policy_number"])

    # Проверка: дата окончания обязательна
    start_date = clean_data.get("start_date")
    end_date = clean_data.get("end_date")
    if not end_date:
        raise ValueError("Поле 'end_date' обязательно для заполнения.")
    if start_date and end_date and end_date < start_date:
        raise ValueError("Дата окончания полиса не может быть меньше даты начала.")

    if payments:
        if not start_date:
            raise ValueError(
                "Поле 'start_date' обязательно при указании платежей."
            )
        first_payment_date = _get_first_payment_date(payments, fallback=start_date)
        if first_payment_date is None:
            raise ValueError("Список платежей должен содержать хотя бы один платёж.")
        if first_payment_date != start_date:
            raise ValueError(
                "Дата первого платежа должна совпадать с датой начала полиса."
            )

    # ────────── Проверка дубликата ──────────
    _check_duplicate_policy(
        clean_data.get("policy_number"),
        client.id,
        deal.id if deal else None,
        clean_data,
    )

    with db.atomic():
        # ────────── Создание полиса ──────────
        policy = Policy.create(client=client, deal=deal, **clean_data)
        logger.info(
            "✅ Полис id=%s №%s создан для клиента '%s'",
            policy.id,
            policy.policy_number,
            client.name,
        )

        # ----------- Платежи ----------
        if payments is not None and len(payments) > 0:
            for p in payments:
                add_payment(
                    policy=policy,
                    amount=Decimal(str(p.get("amount", 0))),
                    payment_date=p.get("payment_date", policy.start_date),
                    actual_payment_date=p.get("actual_payment_date"),
                )
        else:
            # Если список пуст или не передан — автонулевой платёж
            add_payment(
                policy=policy,
                amount=Decimal("0"),
                payment_date=policy.start_date,
            )
            logger.info(
                "💳 Авто-добавлен платёж с нулевой суммой для полиса id=%s №%s",
                policy.id,
                policy.policy_number,
            )

        # отметить платёж как оплаченный, если указано
        if first_payment_paid:
            first_payment = (
                Payment.active()
                .where(Payment.policy == policy)
                .order_by(Payment.payment_date)
                .first()
            )
            if first_payment:
                if first_payment.actual_payment_date is None:
                    first_payment.actual_payment_date = first_payment.payment_date
                    first_payment.save()

                contractor_name = (policy.contractor or "").strip()
                if contractor_name not in {"", "-", "—"}:
                    add_contractor_expense(policy, payments=[first_payment])

    # ────────── Папка полиса ──────────
    deal_description = deal.description if deal else None
    try:
        resolved_gateway = _resolve_gateway(gateway)
        folder_path = create_policy_folder(
            client.name,
            policy.policy_number,
            deal_description,
            gateway=resolved_gateway,
        )
        if folder_path:
            policy.drive_folder_path = folder_path
            policy.save(only=[Policy.drive_folder_path])
            logger.info(
                "📁 Папка полиса id=%s №%s создана: %s",
                policy.id,
                policy.policy_number,
                folder_path,
            )
            open_folder(folder_path)
    except Exception as e:
        logger.error(
            "❌ Ошибка при создании или открытии папки полиса id=%s №%s: %s",
            policy.id,
            policy.policy_number,
            e,
        )

    # ────────── Автоматические действия ──────────
    # Задача продления полиса больше не создаётся автоматически

    _notify_policy_added(policy)
    return policy


# ─────────────────────────── Обновление ───────────────────────────


def update_policy(
    policy: Policy,
    *,
    first_payment_paid: bool = False,
    payments: list[dict] | None = None,
    gateway: DriveGateway | None = None,
    **kwargs,
):
    """Обновить поля полиса и, при необходимости, добавить платежи.

    Args:
        policy: Изменяемый полис.
        first_payment_paid: Отметить ли первый платёж как оплаченный.
        payments: Список платежей для объединения.
        **kwargs: Новые значения полей.

    Returns:
        Policy: Обновлённый полис.
    """
    allowed_fields = {
        "policy_number",
        "insurance_type",
        "insurance_company",
        "contractor",
        "sales_channel",
        "start_date",
        "end_date",
        "vehicle_brand",
        "vehicle_model",
        "vehicle_vin",
        "note",
        "deal",
        "deal_id",
        "client",
        "client_id",
    }

    updates = {}

    old_number = policy.policy_number
    old_deal_id = policy.deal_id
    old_deal_desc = policy.deal.description if policy.deal_id else None
    old_client_name = policy.client.name

    start_date = kwargs.get("start_date", policy.start_date)
    end_date = kwargs.get("end_date", policy.end_date)
    if not end_date:
        raise ValueError("Поле 'end_date' обязательно для заполнения.")
    if start_date and end_date and end_date < start_date:
        raise ValueError("Дата окончания полиса не может быть меньше даты начала.")

    if payments:
        if not start_date:
            raise ValueError(
                "Поле 'start_date' обязательно при указании платежей."
            )
        first_payment_date = _get_first_payment_date(payments, fallback=start_date)
        if first_payment_date is None:
            raise ValueError("Список платежей должен содержать хотя бы один платёж.")
        if first_payment_date != start_date:
            raise ValueError(
                "Дата первого платежа должна совпадать с датой начала полиса."
            )

    # ... дальше стандартная логика ...

    for key, value in kwargs.items():
        if key not in allowed_fields:
            continue
        val = value.strip() if isinstance(value, str) else value
        if key == "deal_id" and "deal" not in kwargs:
            val = get_deal_by_id(val) if val not in ("", None) else None
            key = "deal"
        if key == "client_id" and "client" not in kwargs:
            val = get_client_by_id(val) if val not in ("", None) else None
            key = "client"
        if key == "policy_number" and val not in ("", None):
            val = normalize_policy_number(val)
        if key == "contractor" and val in {"", "-", "—", None}:
            updates[key] = None
            continue
        if val not in ("", None):
            updates[key] = val
        elif key in {"deal", "client"}:
            updates[key] = None

    # ────────── Проверка дубликата ──────────
    new_number = normalize_policy_number(
        updates.get("policy_number", policy.policy_number)
    )
    if "deal" in updates:
        new_deal = updates.get("deal")
        new_deal_id = new_deal.id if new_deal else None
    else:
        new_deal_id = policy.deal_id
    if "client" in updates:
        new_client_id = updates["client"].id if updates["client"] else None
    else:
        new_client_id = policy.client_id
    compare_data = {
        f: updates.get(f, getattr(policy, f))
        for f in allowed_fields
        if f not in {"deal", "deal_id"}
    }

    if not new_number:
        raise ValueError("Поле 'policy_number' обязательно для заполнения.")
    _check_duplicate_policy(
        new_number,
        new_client_id,
        new_deal_id,
        compare_data,
        exclude_id=policy.id,
    )

    if not updates and not first_payment_paid and not payments:
        logger.info(
            "ℹ️ update_policy: нет изменений для полиса id=%s №%s",
            policy.id,
            policy.policy_number,
        )
        return policy

    log_updates = {}
    for key, value in updates.items():
        if isinstance(value, Client):
            log_updates[key] = value.name
        elif isinstance(value, Deal):
            log_updates[key] = value.id
        elif isinstance(value, date):
            log_updates[key] = value.isoformat()
        elif isinstance(value, Decimal):
            log_updates[key] = str(value)
        elif isinstance(value, (str, int, float, bool)) or value is None:
            log_updates[key] = value
        else:
            log_updates[key] = str(value)

    with db.atomic():
        for key, value in updates.items():
            setattr(policy, key, value)
        logger.info(
            "✏️ Обновление полиса id=%s №%s: %s",
            policy.id,
            policy.policy_number,
            log_updates,
        )
        policy.save()
        logger.info(
            "✅ Полис id=%s №%s успешно обновлён",
            policy.id,
            policy.policy_number,
        )

        if payments:
            sync_policy_payments(
                policy,
                [
                    {
                        "payment_date": p.get("payment_date"),
                        "amount": p.get("amount"),
                        "actual_payment_date": p.get("actual_payment_date"),
                    }
                    for p in payments
                ],
            )

        if first_payment_paid:
            first_payment = (
                Payment.select()
                .where((Payment.policy == policy))
                .order_by(Payment.payment_date)
                .first()
            )
            if first_payment:
                if first_payment.actual_payment_date is None:
                    first_payment.actual_payment_date = first_payment.payment_date
                    first_payment.save()

                contractor_name = (policy.contractor or "").strip()
                if contractor_name not in {"", "-", "—"}:
                    add_contractor_expense(policy, payments=[first_payment])

    new_number = policy.policy_number
    new_deal_desc = policy.deal.description if policy.deal_id else None
    new_client_name = policy.client.name
    if (
        old_number != new_number
        or old_deal_desc != new_deal_desc
        or old_client_name != new_client_name
    ):
        try:
            from services.folder_utils import rename_policy_folder

            resolved_gateway = _resolve_gateway(gateway)
            new_path, new_link = rename_policy_folder(
                old_client_name,
                old_number,
                old_deal_desc,
                new_client_name,
                new_number,
                new_deal_desc,
                policy.drive_folder_link
                if is_drive_link(policy.drive_folder_link)
                else None,
                gateway=resolved_gateway,
            )
            fields_to_update = []
            if new_path and new_path != policy.drive_folder_path:
                policy.drive_folder_path = new_path
                fields_to_update.append(Policy.drive_folder_path)
            if new_link and new_link != policy.drive_folder_link:
                policy.drive_folder_link = new_link
                fields_to_update.append(Policy.drive_folder_link)
            if fields_to_update:
                policy.save(only=fields_to_update)
        except Exception:
            logger.exception(
                "Не удалось переименовать папку полиса id=%s №%s",
                policy.id,
                policy.policy_number,
            )

    if policy.deal_id and policy.deal_id != old_deal_id:
        _notify_policy_added(policy)
    return policy


# ─────────────────────────── Пролонгация ───────────────────────────


def prolong_policy(original_policy: Policy) -> Policy:
    if not original_policy.start_date or not original_policy.end_date:
        raise ValueError("У полиса должны быть указаны даты начала и окончания.")

    new_policy = Policy.create(
        client=original_policy.client,
        deal=original_policy.deal,
        policy_number=None,
        insurance_company=original_policy.insurance_company,
        insurance_type=original_policy.insurance_type,
        start_date=original_policy.start_date + timedelta(days=365),
        end_date=original_policy.end_date + timedelta(days=365),
        note=original_policy.note,
        status="новый",
    )

    original_policy.renewed_to = new_policy.start_date
    original_policy.save()

    return new_policy


def build_policy_query(
    search_text: str = "",
    show_deleted: bool = False,
    deal_id: int | None = None,
    client_id: int | None = None,
    include_renewed: bool = True,
    without_deal_only: bool = False,
    column_filters: dict | None = None,
    order_by: Field | str | None = None,
    **filters,
):
    """Сформировать запрос для выборки полисов с фильтрами."""
    base = Policy.active() if not show_deleted else Policy.select()
    query = (
        base.select(Policy, Client, Deal)
        .join(Client)
        .switch(Policy)
        .join(Deal, JOIN.LEFT_OUTER)
    )
    if deal_id is not None:
        query = query.where(Policy.deal_id == deal_id)
    if client_id is not None:
        query = query.where(Policy.client == client_id)
    if not include_renewed:
        query = query.where(
            (Policy.renewed_to.is_null(True))
            | (Policy.renewed_to == "")
            | (Policy.renewed_to == "Нет")
        )
    if deal_id is None and without_deal_only:
        query = query.where(Policy.deal_id.is_null(True))
    query = apply_search_and_filters(query, Policy, search_text, column_filters)
    return query


def get_policy_by_id(policy_id: int) -> Policy | None:
    """Получить полис по идентификатору.

    Args:
        policy_id: Идентификатор полиса.

    Returns:
        Policy | None: Найденный полис или ``None``.
    """
    return Policy.active().where(Policy.id == policy_id).get_or_none()


def get_unique_policy_field_values(field_name: str) -> list[str]:
    """Получить уникальные значения указанного поля полиса.

    Args:
        field_name: Имя поля модели ``Policy``.

    Returns:
        list[str]: Список уникальных значений.
    """
    # Проверка, что поле допустимо
    allowed_fields = {
        "vehicle_brand",
        "vehicle_model",
        "sales_channel",
        "contractor",
        "insurance_company",
        "insurance_type",
    }
    if field_name not in allowed_fields:
        raise ValueError(f"Недопустимое поле для выборки: {field_name}")
    # Получить уникальные значения
    q = (
        Policy.select(getattr(Policy, field_name))
        .where(getattr(Policy, field_name).is_null(False))
        .distinct()
    )
    return sorted({getattr(p, field_name) for p in q if getattr(p, field_name)})


def attach_premium(policies: list[Policy]) -> None:
    """Добавить атрибут ``_premium`` со суммой платежей."""
    if not policies:
        return
    ids = [p.id for p in policies]
    sub = (
        Payment.active()
        .select(Payment.policy, fn.SUM(Payment.amount).alias("total"))
        .where(Payment.policy.in_(ids))
        .group_by(Payment.policy)
    )
    totals = {row.policy_id: row.total for row in sub}
    for p in policies:
        setattr(p, "_premium", totals.get(p.id, Decimal("0")) or Decimal("0"))
