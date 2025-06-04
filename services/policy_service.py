"""Функционал CRUD и вспомогательные операции для полисов."""

import logging
from datetime import timedelta

from peewee import ModelSelect, fn

from database.db import db
from database.models import Client  # если ещё не импортирован
from database.models import Income, Payment, Policy
from services.client_service import get_client_by_id
from services.deal_service import get_deal_by_id
from services.folder_utils import create_policy_folder, open_folder
from services.income_service import add_income
from services.payment_service import add_payment
from services.task_service import add_task

logger = logging.getLogger(__name__)

# ───────────────────────── базовые CRUD ─────────────────────────



def get_all_policies() -> ModelSelect:
    """Вернуть все полисы без удалённых."""
    return Policy.select().where(Policy.is_deleted == False)


def get_policies_by_client_id(client_id: int) -> ModelSelect:
    """Полисы клиента по его ``id``."""
    return Policy.select().where(
        (Policy.client_id == client_id) & (Policy.is_deleted == False)
    )


def get_policies_by_deal_id(deal_id: int) -> ModelSelect:
    """Полисы, связанные со сделкой."""
    return (
        Policy
        .select()
        .where(
            (Policy.deal_id == deal_id) &
            (Policy.is_deleted == False)
        )
        .order_by(Policy.start_date.asc())
    )



def get_policy_by_number(policy_number: str) -> Policy | None:
    """Найти полис по его номеру."""
    return Policy.get_or_none(Policy.policy_number == policy_number)




def get_policies_page(
    page: int,
    per_page: int,
    search_text: str = "",
    show_deleted: bool = False,
    deal_id: int | None = None,
    client_id: int | None = None,
    order_by: str = "start_date",
    order_dir: str = "asc",
    **filters,
) -> ModelSelect:
    """Вернуть страницу полисов с учётом фильтров."""
    query = build_policy_query(
        search_text=search_text,
        show_deleted=show_deleted,
        deal_id=deal_id,
        client_id=client_id,
        **filters
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






def mark_policy_deleted(policy_id: int) -> None:
    """Пометить полис как удалённый."""
    policy = Policy.get_or_none(Policy.id == policy_id)
    if policy:
        policy.is_deleted = True
        policy.save()
    else:
        logger.warning("❗ Полис с id=%s не найден для удаления", policy_id)


# ─────────────────────────── Добавление ───────────────────────────

def add_policy(*, payments=None, first_payment_paid: bool = False, **kwargs) -> Policy:

    """
    Создаёт новый полис с привязкой к клиенту и (опционально) сделке.
    Обязательно принимает хотя бы один платёж (payments),
    если не передан — создаёт авто-нулевой платёж на дату начала.
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

    # Проверка: дата окончания обязательна
    start_date = clean_data.get("start_date")
    end_date = clean_data.get("end_date")
    if not end_date:
        raise ValueError("Поле 'end_date' обязательно для заполнения.")
    if start_date and end_date and end_date < start_date:
        raise ValueError("Дата окончания полиса не может быть меньше даты начала.")

    # ────────── Создание полиса ──────────
    policy = Policy.create(
        client=client,
        deal=deal,
        is_deleted=False,
        **clean_data
    )
    logger.info("✅ Полис #%s создан для клиента '%s'", policy.policy_number, client.name)

    # ────────── Папка полиса ──────────
    deal_description = deal.description if deal else None
    try:
        folder_path = create_policy_folder(client.name, policy.policy_number, deal_description)
        if folder_path:
            policy.drive_folder_link = folder_path
            policy.save()
            logger.info("📁 Папка полиса создана: %s", folder_path)
            open_folder(folder_path)
    except Exception as e:
        logger.error("❌ Ошибка при создании или открытии папки полиса: %s", e)



    # ────────── Автоматические действия ──────────
    if policy.start_date and policy.end_date:
        add_task(
            title="продлить полис",
            due_date=policy.end_date - timedelta(days=30),
            policy_id=policy.id,
            is_done=False,
            deal_id=policy.deal_id
        )
        logger.info("📝 Добавлена задача продления для полиса #%s за 30 дней до его окончания", policy.policy_number)

    # ----------- Платежи ----------
    from services.payment_service import add_payment

    if payments is not None and len(payments) > 0:
        for p in payments:
            add_payment(
                policy=policy,
                amount=p.get("amount", 0),
                payment_date=p.get("payment_date", policy.start_date)
            )
    else:
        # Если список пуст или не передан — автонулевой платёж
        add_payment(
            policy=policy,
            amount=0,
            payment_date=policy.start_date
        )
        logger.info("💳 Авто-добавлен платёж с нулевой суммой для полиса #%s", policy.policy_number)
        # отметить платёж как оплаченный, если указано
    if first_payment_paid:
        first_payment = policy.payments.order_by(Payment.payment_date).first()
        if first_payment:
            first_payment.is_paid = True
            first_payment.save()

    # ────────── Доход по первой рассрочке, если оплачен ──────────
    

    if first_payment_paid:
        first_payment = policy.payments.order_by(Payment.payment_date).first()
        if first_payment and not first_payment.incomes.exists():
            add_income(
                payment_id=first_payment.id,
                amount=first_payment.amount,
                received_date=first_payment.payment_date,
                note="Доход получен при добавлении полиса"
            )



    return policy




# ─────────────────────────── Обновление ───────────────────────────

def update_policy(policy: Policy, **kwargs) -> Policy:
    """Изменить параметры существующего полиса."""
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
    }

    updates = {}

    
    start_date = kwargs.get("start_date", policy.start_date)
    end_date = kwargs.get("end_date", policy.end_date)
    if not end_date:
        raise ValueError("Поле 'end_date' обязательно для заполнения.")
    if start_date and end_date and end_date < start_date:
        raise ValueError("Дата окончания полиса не может быть меньше даты начала.")
    # ... дальше стандартная логика ...


    for key, value in kwargs.items():
        if key in allowed_fields and value not in ("", None):
            if key == "deal_id" and not kwargs.get("deal"):
                value = get_deal_by_id(value)
                key = "deal"
            updates[key] = value

    if not updates:
        logger.info("ℹ️ update_policy: нет изменений для полиса #%s", policy.id)
        return policy

    for key, value in updates.items():
        setattr(policy, key, value)
    logger.info("✏️ Обновление полиса #%s: %s", policy.id, updates)
    policy.save()
    logger.info("✅ Полис #%s успешно обновлён", policy.id)
    
    return policy


# ─────────────────────────── Пролонгация ───────────────────────────

def prolong_policy(original_policy: Policy) -> Policy:
    """Создать новый полис на основе предыдущего."""
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
        is_deleted=False
    )

    original_policy.renewed_to = new_policy.start_date
    original_policy.save()

    return new_policy


def apply_policy_filters(
    query: ModelSelect,
    search_text: str = "",
    show_deleted: bool = False,
    deal_id: int | None = None,
    client_id: int | None = None,
) -> ModelSelect:
    """Применить фильтры к выборке полисов."""
    if deal_id is not None:
        query = query.where(Policy.deal_id == deal_id)
    if client_id is not None:
        query = query.where(Policy.client == client_id)
    if not show_deleted:
        query = query.where(Policy.is_deleted == False)
    if search_text:
        query = query.where(
            (Policy.policy_number.contains(search_text)) |
            (Client.name.contains(search_text))
        )
    return query


def build_policy_query(
    search_text: str = "",
    show_deleted: bool = False,
    deal_id: int | None = None,
    client_id: int | None = None,
    **filters,
) -> ModelSelect:
    """Базовый запрос полисов с JOIN клиентом."""
    query = Policy.select(Policy, Client).join(Client)
    return apply_policy_filters(query, search_text, show_deleted, deal_id, client_id)



def get_policy_by_id(policy_id: int) -> Policy | None:
    """Получить полис по ``id``."""
    return Policy.get_or_none((Policy.id == policy_id) & (Policy.is_deleted == False))



def get_unique_policy_field_values(field_name: str) -> list[str]:
    """Вернуть отсортированный список уникальных значений указанного поля."""
    # Проверка, что поле допустимо
    allowed_fields = {
        "vehicle_brand", "vehicle_model",
        "sales_channel", "contractor",
        "insurance_company", "insurance_type",
    }
    if field_name not in allowed_fields:
        raise ValueError(f"Недопустимое поле для выборки: {field_name}")
    # Получить уникальные значения
    q = (Policy
         .select(getattr(Policy, field_name))
         .where(getattr(Policy, field_name).is_null(False))
         .distinct())
    return sorted({getattr(p, field_name) for p in q if getattr(p, field_name)})
