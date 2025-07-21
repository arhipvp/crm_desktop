from __future__ import annotations

"""Deal service module — CRUD‑операции и вспомогательные функции для сущности Deal.
Исправлено:
• Папка сделки создаётся через create_deal_folder() с гарантированным префиксом «Сделка - …».
• Сохранение локального пути производится в поле ``drive_folder_path`` (обновите модель ``Deal``).
• Удалён неиспользуемый импорт DealStatus.
• Типизация и мелкие правки PEP 8.
"""
import logging
from datetime import date
from utils.time_utils import now_str

from peewee import ModelSelect  # если ещё не импортирован

from database.db import db
from database.models import Client  # обязательно!
from database.models import Deal, Policy, Task
from services.client_service import get_client_by_id
from services.folder_utils import (
    create_deal_folder,
    find_drive_folder,
    sanitize_name,
    extract_folder_id,
    Credentials,
)

logger = logging.getLogger(__name__)

# ──────────────────────────── Получение ─────────────────────────────


def get_all_deals():
    """Возвращает все сделки, кроме помеченных как удалённые."""
    return Deal.select().where(Deal.is_deleted == False)


def get_open_deals():
    """Открытые (не закрытые) сделки, не помеченные как удалённые."""
    return Deal.select().where((Deal.is_closed == False) & (Deal.is_deleted == False))


def get_deals_by_client_id(client_id: int):
    return Deal.select().where(
        (Deal.client_id == client_id) & (Deal.is_deleted == False)
    )


def get_deal_by_id(deal_id: int) -> Deal | None:
    return Deal.get_or_none((Deal.id == deal_id) & (Deal.is_deleted == False))


# ──────────────────────────── Добавление ─────────────────────────────


def add_deal(**kwargs):
    """Создаёт новую сделку.

    Обязательные поля: ``client_id``, ``start_date``, ``description``.
    После создания создаётся локальная папка сделки «Сделка - …» внутри папки клиента;
    путь сохраняется в ``deal.drive_folder_path``.
    """

    required_fields = {"client_id", "start_date", "description"}
    missing = [f for f in required_fields if not kwargs.get(f)]
    if missing:
        raise ValueError(f"Отсутствуют обязательные поля: {', '.join(missing)}")

    client = get_client_by_id(kwargs["client_id"])
    if not client:
        raise ValueError("Клиент не найден.")

    allowed_fields = {
        "start_date",
        "status",
        "description",
        "calculations",
        "reminder_date",
        "is_closed",
        "closed_reason",
    }

    clean_data: dict = {
        key: kwargs[key]
        for key in allowed_fields
        if key in kwargs and kwargs[key] not in ("", None)
    }

    if "calculations" in clean_data:
        ts = now_str()
        clean_data["calculations"] = f"[{ts}]: {clean_data['calculations']}"

    # FK клиент
    clean_data["client"] = client
    clean_data["is_deleted"] = False

    with db.atomic():
        deal: Deal = Deal.create(**clean_data)
        logger.info(
            "✅ Сделка #%s создана: клиент %s — %s",
            deal.id,
            client.name,
            deal.description,
        )

        # ───── создание папки сделки ─────
        try:
            local_path, web_link = create_deal_folder(
                client.name,
                deal.description,
                client_drive_link=client.drive_folder_link,
            )
            logger.info("📁 Папка сделки создана: %s", local_path)
            if web_link:
                logger.info("🔗 Google Drive-ссылка сделки: %s", web_link)
            deal.drive_folder_path = local_path
            deal.drive_folder_link = web_link
            deal.save()
        except Exception as e:
            logger.error("❌ Ошибка создания папки сделки: %s", e)

        return deal


def add_deal_from_policy(policy: Policy) -> Deal:
    """Создаёт сделку на основе полиса и привязывает полис к ней."""

    parts = []
    if policy.insurance_type:
        parts.append(policy.insurance_type)
    if policy.vehicle_brand:
        brand = policy.vehicle_brand
        if policy.vehicle_model:
            brand += f" {policy.vehicle_model}"
        parts.append(brand)
    description = " ".join(parts).strip() or f"Из полиса {policy.policy_number}"

    deal = add_deal(
        client_id=policy.client_id,
        start_date=policy.start_date,
        description=description,
        reminder_date=date.today(),
    )

    try:
        from services.folder_utils import move_policy_folder_to_deal

        new_path = move_policy_folder_to_deal(
            policy.drive_folder_link,
            policy.client.name,
            deal.description,
        )
        if new_path:
            policy.drive_folder_link = new_path
    except Exception:
        logger.exception("Не удалось переместить папку полиса")

    policy.deal = deal
    policy.save()
    return deal


# ──────────────────────────── Обновление ─────────────────────────────


def update_deal(deal: Deal, *, journal_entry: str | None = None, **kwargs):
    """Обновляет сделку.

    Параметр ``journal_entry`` добавляет запись в журнал ``Deal.calculations``.
    Передаваемый ``calculations`` трактуется как текст расчёта и сохраняется в
    таблицу :class:`DealCalculation`.
    """

    allowed_fields = {
        "start_date",
        "status",
        "description",
        "reminder_date",
        "is_closed",
        "closed_reason",
        "client_id",
    }

    old_client_name = deal.client.name if deal.client_id else None
    old_desc = deal.description

    # Собираем простые обновления (кроме calculations)
    updates: dict = {
        key: kwargs[key]
        for key in allowed_fields
        if key in kwargs and kwargs[key] not in ("", None)
    }

    # Смена клиента
    if "client_id" in updates:
        client = get_client_by_id(updates.pop("client_id"))
        if not client:
            raise ValueError("Клиент не найден.")
        deal.client = client

    # calculations -> отдельная таблица
    new_calc: str | None = kwargs.get("calculations")
    new_note: str | None = journal_entry

    # Если закрываем сделку — пишем причину в журнал
    if kwargs.get("is_closed") and kwargs.get("closed_reason"):
        reason = kwargs["closed_reason"]
        ts = now_str()
        auto_note = f"[{ts}]: Сделка закрыта. Причина: {reason}"
        old = deal.calculations or ""
        deal.calculations = f"{auto_note}\n{old}"

    # Добавляем произвольную запись в журнал
    if new_note:
        ts = now_str()
        entry = f"[{ts}]: {new_note}"
        old = deal.calculations or ""
        deal.calculations = f"{entry}\n{old}" if old else entry

    # Если нечего обновлять — возвращаем сделку как есть
    if not updates and not new_calc and not new_note:
        return deal

    # Применяем простые обновления
    for key, value in updates.items():
        setattr(deal, key, value)

    deal.save()

    # Переименование папки при изменении описания или клиента
    new_client_name = deal.client.name if deal.client_id else None
    new_desc = deal.description
    if (
        (old_client_name and new_client_name and old_client_name != new_client_name)
        or old_desc != new_desc
    ):
        try:
            from services.folder_utils import rename_deal_folder

            new_path, _ = rename_deal_folder(
                old_client_name or "",
                old_desc,
                new_client_name or "",
                new_desc,
                deal.drive_folder_link,
                deal.drive_folder_path,
            )
            if new_path and new_path != deal.drive_folder_path:
                deal.drive_folder_path = new_path
                deal.save(only=[Deal.drive_folder_path, Deal.drive_folder_link])
        except Exception:
            logger.exception("Не удалось переименовать папку сделки")

    # Добавляем расчётную запись
    if new_calc:
        from services.calculation_service import add_calculation
        add_calculation(deal.id, note=new_calc)
    return deal


# ──────────────────────────── Удаление ─────────────────────────────


def mark_deal_deleted(deal_id: int):
    deal = Deal.get_or_none(Deal.id == deal_id)
    if deal:
        deal.is_deleted = True
        deal.save()
        try:
            from services.folder_utils import rename_deal_folder

            new_desc = f"{deal.description} deleted"
            new_path, _ = rename_deal_folder(
                deal.client.name,
                deal.description,
                deal.client.name,
                new_desc,
                deal.drive_folder_link,
                deal.drive_folder_path,
            )
            deal.description = new_desc
            deal.drive_folder_path = new_path
            deal.save(
                only=[Deal.description, Deal.drive_folder_path, Deal.is_deleted]
            )
        except Exception:
            logger.exception("Не удалось пометить папку сделки удалённой")
    else:
        logger.warning("❗ Сделка с id=%s не найдена для удаления", deal_id)


def apply_deal_filters(
    query,
    search_text: str = "",
    show_deleted: bool = False,
    column_filters: dict[str, str] | None = None,
):
    if not show_deleted:
        query = query.where(Deal.is_deleted == False)
    if search_text:
        query = query.where(
            (Deal.description.contains(search_text))
            | (Deal.status.contains(search_text))
            | (Client.name.contains(search_text))
            | (Deal.calculations.contains(search_text))
        )
    from services.query_utils import apply_column_filters

    query = apply_column_filters(query, column_filters, Deal)
    return query


# ──────────────────────────── Пагинация ─────────────────────────────


def get_deals_page(
    page: int,
    per_page: int,
    search_text: str = "",
    show_deleted: bool = False,
    order_by: str = "reminder_date",
    order_dir: str = "asc",
    column_filters: dict[str, str] | None = None,
    **filters,
) -> ModelSelect:
    """Вернуть страницу сделок с указанными фильтрами."""
    query = build_deal_query(column_filters=column_filters, **filters)

    query = apply_deal_filters(query, search_text, show_deleted, column_filters)

    # 👉 Только один order_by
    if order_by and hasattr(Deal, order_by):
        order_field = getattr(Deal, order_by)
        if order_dir == "desc":
            query = query.order_by(order_field.desc())
        else:
            query = query.order_by(order_field.asc())
    else:
        query = query.order_by(Deal.start_date.desc())

    from peewee import prefetch
    from database.models import DealExecutor, Executor

    offset = (page - 1) * per_page
    page_query = query.limit(per_page).offset(offset)
    items = list(prefetch(page_query, DealExecutor, Executor))
    for deal in items:
        ex = deal.executors[0].executor if getattr(deal, "executors", []) else None
        setattr(deal, "_executor", ex)
    return items


def get_open_deals_page(page: int = 1, per_page: int = 50) -> ModelSelect:
    """Возвращает открытые сделки постранично."""
    return (
        Deal.select()
        .where((Deal.is_closed == False) & (Deal.is_deleted == False))
        .order_by(Deal.start_date.desc())
        .paginate(page, per_page)
    )


# ──────────────────────────── Связанные сущности ─────────────────────────────


def get_policies_by_deal_id(deal_id: int) -> ModelSelect:
    """Вернуть полисы, привязанные к сделке."""
    return Policy.select().where(
        (Policy.deal == deal_id) & (Policy.is_deleted == False)
    )


def get_tasks_by_deal_id(deal_id: int) -> ModelSelect:
    """Вернуть задачи, связанные со сделкой."""
    return Task.select().where((Task.deal == deal_id) & (Task.is_deleted == False))


def build_deal_query(
    search_text: str = "",
    show_deleted: bool = False,
    show_closed: bool = False,
    column_filters: dict[str, str] | None = None,
) -> ModelSelect:
    """Базовый запрос сделок с фильтрами по статусам."""
    query = Deal.select().join(Client)

    query = apply_deal_filters(query, search_text, show_deleted, column_filters)

    if not show_closed:
        query = query.where(Deal.is_closed == False)

    return query


def get_next_deal(current_deal: Deal) -> Deal | None:
    """Найти следующую сделку по дате напоминания."""
    if current_deal.reminder_date is None:
        return None

    return (
        get_open_deals()
        .where(
            (Deal.reminder_date > current_deal.reminder_date)
            | (
                (Deal.reminder_date == current_deal.reminder_date)
                & (Deal.id > current_deal.id)
            )
        )
        .order_by(Deal.reminder_date.asc(), Deal.id.asc())
        .first()
    )


def get_prev_deal(current_deal: Deal) -> Deal | None:
    """Найти предыдущую сделку по дате напоминания."""
    if current_deal.reminder_date is None:
        return None

    return (
        get_open_deals()
        .where(
            (Deal.reminder_date < current_deal.reminder_date)
            | (
                (Deal.reminder_date == current_deal.reminder_date)
                & (Deal.id < current_deal.id)
            )
        )
        .order_by(Deal.reminder_date.desc(), Deal.id.desc())
        .first()
    )


def refresh_deal_drive_link(deal: Deal) -> None:
    """Попытаться найти ссылку папки сделки на Google Drive."""
    if deal.drive_folder_link:
        return

    client_link = deal.client.drive_folder_link if deal.client else None
    if not client_link or Credentials is None:
        return

    try:
        deal_name = sanitize_name(f"Сделка - {deal.description}")
        parent_id = extract_folder_id(client_link)
        if not parent_id:
            return
        link = find_drive_folder(deal_name, parent_id)
        if link:
            deal.drive_folder_link = link
            deal.save(only=[Deal.drive_folder_link])
            logger.info("🔗 Обновлена ссылка сделки на Drive: %s", link)
    except Exception:
        logger.exception("Не удалось обновить ссылку на папку сделки %s", deal.id)
