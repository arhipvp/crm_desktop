"""Сервис управления страховыми полисами."""

import logging
from datetime import timedelta
from peewee import fn


from database.models import Client  # если ещё не импортирован
from database.models import Payment, Policy
from services.client_service import get_client_by_id
from services.deal_service import get_deal_by_id
from services.folder_utils import create_policy_folder, open_folder
from services.payment_service import add_payment

logger = logging.getLogger(__name__)

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
    return Policy.select().where(Policy.is_deleted == False)


def get_policies_by_client_id(client_id: int):
    """Полисы, принадлежащие клиенту.

    Args:
        client_id: Идентификатор клиента.

    Returns:
        ModelSelect: Выборка полисов клиента.
    """
    return Policy.select().where(
        (Policy.client_id == client_id) & (Policy.is_deleted == False)
    )


def get_policies_by_deal_id(deal_id: int):
    """Полисы, связанные со сделкой.

    Args:
        deal_id: Идентификатор сделки.

    Returns:
        ModelSelect: Выборка полисов.
    """
    return (
        Policy.select()
        .where((Policy.deal_id == deal_id) & (Policy.is_deleted == False))
        .order_by(Policy.start_date.asc())
    )


def get_policy_by_number(policy_number: str):
    """Найти полис по его номеру.

    Args:
        policy_number: Номер полиса.

    Returns:
        Policy | None: Найденный полис либо ``None``.
    """
    return Policy.get_or_none(Policy.policy_number == policy_number)


def _check_duplicate_policy(policy_number: str, client_id: int, deal_id: int | None, data: dict, *, exclude_id: int | None = None) -> None:
    """Проверить наличие дубликата и, если найден, поднять ``ValueError``.

    Сравниваются ключевые поля полиса. Если все совпадают - сообщение сообщает
    об идентичности, иначе перечисляются отличающиеся поля.
    """

    if not policy_number:
        return

    cond = Policy.policy_number == policy_number
    if exclude_id is not None:
        cond &= Policy.id != exclude_id

    existing = Policy.get_or_none(cond)
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


def get_policies_page(
    page,
    per_page,
    search_text="",
    show_deleted=False,
    deal_id=None,
    client_id=None,
    order_by="start_date",
    order_dir="asc",
    include_renewed=True,
    without_deal_only=False,
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

    Returns:
        ModelSelect: Отфильтрованная выборка полисов.
    """
    query = build_policy_query(
        search_text=search_text,
        show_deleted=show_deleted,
        deal_id=deal_id,
        client_id=client_id,
        include_renewed=include_renewed,
        without_deal_only=without_deal_only,
        **filters,
    )
    # Выбираем поле сортировки
    if hasattr(Policy, order_by):
        order_field = getattr(Policy, order_by)
        if order_dir == "desc":
            query = query.order_by(order_field.desc())
        else:
            query = query.order_by(order_field.asc())
    else:
        query = query.order_by(Policy.start_date.asc())
    offset = (page - 1) * per_page
    return query.offset(offset).limit(per_page)


def mark_policy_deleted(policy_id: int):
    policy = Policy.get_or_none(Policy.id == policy_id)
    if policy:
        policy.is_deleted = True
        policy.save()
        try:
            from services.folder_utils import rename_policy_folder

            new_number = f"{policy.policy_number} deleted"
            new_path, _ = rename_policy_folder(
                policy.client.name,
                policy.policy_number,
                policy.deal.description if policy.deal_id else None,
                policy.client.name,
                new_number,
                policy.deal.description if policy.deal_id else None,
                policy.drive_folder_link,
            )
            policy.policy_number = new_number
            if new_path:
                policy.drive_folder_link = new_path
            policy.save(
                only=[Policy.policy_number, Policy.drive_folder_link, Policy.is_deleted]
            )
        except Exception:
            logger.exception("Не удалось пометить папку полиса удалённой")
    else:
        logger.warning("❗ Полис с id=%s не найден для удаления", policy_id)


def mark_policies_deleted(policy_ids: list[int]) -> int:
    """Массово помечает полисы удалёнными."""
    if not policy_ids:
        return 0

    count = 0
    for pid in policy_ids:
        before = Policy.get_or_none(Policy.id == pid)
        if before and not before.is_deleted:
            mark_policy_deleted(pid)
            count += 1

    return count


def mark_policy_renewed(policy_id: int):
    """Пометить полис как продлённый без привязки к новому."""
    policy = Policy.get_or_none(Policy.id == policy_id)
    if policy:
        policy.renewed_to = True
        policy.save()
        logger.info("🔁 Полис %s помечен продлённым", policy_id)
    else:
        logger.warning("❗ Полис с id=%s не найден для продления", policy_id)


def mark_policies_renewed(policy_ids: list[int]) -> int:
    """Массово пометить полисы как продлённые без привязки к новому."""
    if not policy_ids:
        return 0
    return (
        Policy.update(renewed_to=True)
        .where(Policy.id.in_(policy_ids))
        .execute()
    )


# ─────────────────────────── Добавление ───────────────────────────


def add_policy(*, payments=None, first_payment_paid=False, **kwargs):
    """
    Создаёт новый полис с привязкой к клиенту и (опционально) сделке.
    Требует указать номер полиса и хотя бы один платёж (payments).
    Если список платежей не передан, создаётся авто-нулевой платёж
    на дату начала.
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

    clean_data = {
        field: kwargs[field]
        for field in allowed_fields
        if field in kwargs and kwargs[field] not in ("", None)
    }

    # Обязателен номер полиса
    if not clean_data.get("policy_number"):
        raise ValueError("Поле 'policy_number' обязательно для заполнения.")

    # Проверка: дата окончания обязательна
    start_date = clean_data.get("start_date")
    end_date = clean_data.get("end_date")
    if not end_date:
        raise ValueError("Поле 'end_date' обязательно для заполнения.")
    if start_date and end_date and end_date < start_date:
        raise ValueError("Дата окончания полиса не может быть меньше даты начала.")

    # ────────── Проверка дубликата ──────────
    _check_duplicate_policy(
        clean_data.get("policy_number"),
        client.id,
        deal.id if deal else None,
        clean_data,
    )

    # ────────── Создание полиса ──────────
    policy = Policy.create(client=client, deal=deal, is_deleted=False, **clean_data)
    logger.info(
        "✅ Полис #%s создан для клиента '%s'", policy.policy_number, client.name
    )

    # ────────── Папка полиса ──────────
    deal_description = deal.description if deal else None
    try:
        folder_path = create_policy_folder(
            client.name, policy.policy_number, deal_description
        )
        if folder_path:
            policy.drive_folder_link = folder_path
            policy.save()
            logger.info("📁 Папка полиса создана: %s", folder_path)
            open_folder(folder_path)
    except Exception as e:
        logger.error("❌ Ошибка при создании или открытии папки полиса: %s", e)

    # ────────── Автоматические действия ──────────
    # Задача продления полиса больше не создаётся автоматически

    # ----------- Платежи ----------

    if payments is not None and len(payments) > 0:
        for p in payments:
            add_payment(
                policy=policy,
                amount=p.get("amount", 0),
                payment_date=p.get("payment_date", policy.start_date),
            )
    else:
        # Если список пуст или не передан — автонулевой платёж
        add_payment(policy=policy, amount=0, payment_date=policy.start_date)
        logger.info(
            "💳 Авто-добавлен платёж с нулевой суммой для полиса #%s",
            policy.policy_number,
        )

    # отметить платёж как оплаченный, если указано
    if first_payment_paid:
        first_payment = policy.payments.order_by(Payment.payment_date).first()
        if first_payment and first_payment.actual_payment_date is None:
            first_payment.actual_payment_date = first_payment.payment_date
            first_payment.save()

    return policy


# ─────────────────────────── Обновление ───────────────────────────


def update_policy(policy: Policy, *, first_payment_paid: bool = False, **kwargs):
    """Обновить поля полиса.

    Args:
        policy: Изменяемый полис.
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
    old_deal_desc = policy.deal.description if policy.deal_id else None
    old_client_name = policy.client.name

    start_date = kwargs.get("start_date", policy.start_date)
    end_date = kwargs.get("end_date", policy.end_date)
    if not end_date:
        raise ValueError("Поле 'end_date' обязательно для заполнения.")
    if start_date and end_date and end_date < start_date:
        raise ValueError("Дата окончания полиса не может быть меньше даты начала.")

    # ... дальше стандартная логика ...

    for key, value in kwargs.items():
        if key not in allowed_fields:
            continue
        if key == "deal_id" and "deal" not in kwargs:
            value = get_deal_by_id(value) if value not in ("", None) else None
            key = "deal"
        if key == "client_id" and "client" not in kwargs:
            value = get_client_by_id(value) if value not in ("", None) else None
            key = "client"
        if value not in ("", None):
            updates[key] = value
        elif key in {"contractor", "deal", "client"}:
            updates[key] = None

    # ────────── Проверка дубликата ──────────
    new_number = updates.get("policy_number", policy.policy_number)
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

    if not updates and not first_payment_paid:
        logger.info("ℹ️ update_policy: нет изменений для полиса #%s", policy.id)
        return policy

    for key, value in updates.items():
        setattr(policy, key, value)
    logger.info("✏️ Обновление полиса #%s: %s", policy.id, updates)
    policy.save()
    logger.info("✅ Полис #%s успешно обновлён", policy.id)

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

            new_path, _ = rename_policy_folder(
                old_client_name,
                old_number,
                old_deal_desc,
                new_client_name,
                new_number,
                new_deal_desc,
                policy.drive_folder_link,
            )
            if new_path and new_path != policy.drive_folder_link:
                policy.drive_folder_link = new_path
                policy.save(only=[Policy.drive_folder_link])
        except Exception:
            logger.exception("Не удалось переименовать папку полиса")

    if first_payment_paid:
        first_payment = policy.payments.order_by(Payment.payment_date).first()
        if first_payment and first_payment.actual_payment_date is None:
            first_payment.actual_payment_date = first_payment.payment_date
            first_payment.save()

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
        is_deleted=False,
    )

    original_policy.renewed_to = new_policy.start_date
    original_policy.save()

    return new_policy


def apply_policy_filters(
    query,
    search_text: str = "",
    show_deleted: bool = False,
    deal_id: int | None = None,
    client_id: int | None = None,
    include_renewed: bool = True,
    without_deal_only: bool = False,
    column_filters: dict[str, str] | None = None,
):
    if deal_id is not None:
        query = query.where(Policy.deal_id == deal_id)
    if client_id is not None:
        query = query.where(Policy.client == client_id)
    if not show_deleted:
        query = query.where(Policy.is_deleted == False)
    if not include_renewed:
        query = query.where(
            (Policy.renewed_to.is_null(True))
            | (Policy.renewed_to == "")
            | (Policy.renewed_to == "Нет")
        )
    if deal_id is None and without_deal_only:
        query = query.where(Policy.deal_id.is_null(True))
    if search_text:
        query = query.where(
            (Policy.policy_number.contains(search_text))
            | (Client.name.contains(search_text))
        )

    from services.query_utils import apply_column_filters

    query = apply_column_filters(query, column_filters, Policy)
    return query


def build_policy_query(
    search_text: str = "",
    show_deleted: bool = False,
    deal_id: int | None = None,
    client_id: int | None = None,
    include_renewed: bool = True,
    without_deal_only: bool = False,
    column_filters: dict[str, str] | None = None,
    **filters,
):
    """Сформировать запрос для выборки полисов с фильтрами."""
    query = Policy.select(Policy, Client).join(Client)
    return apply_policy_filters(
        query,
        search_text,
        show_deleted,
        deal_id,
        client_id,
        include_renewed,
        without_deal_only,
        column_filters,
    )


def get_policy_by_id(policy_id: int) -> Policy | None:
    """Получить полис по идентификатору.

    Args:
        policy_id: Идентификатор полиса.

    Returns:
        Policy | None: Найденный полис или ``None``.
    """
    return Policy.get_or_none((Policy.id == policy_id) & (Policy.is_deleted == False))


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
        Payment.select(Payment.policy, fn.SUM(Payment.amount).alias("total"))
        .where((Payment.policy.in_(ids)) & (Payment.is_deleted == False))
        .group_by(Payment.policy)
    )
    totals = {row.policy_id: row.total for row in sub}
    for p in policies:
        setattr(p, "_premium", totals.get(p.id, 0) or 0)
