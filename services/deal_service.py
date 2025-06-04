from __future__ import annotations

"""Deal service module — CRUD‑операции и вспомогательные функции для сущности Deal.
Исправлено:
• Папка сделки создаётся через create_deal_folder() с гарантированным префиксом «Сделка - …».
• Сохранение локального пути производится в поле ``drive_folder_path`` (обновите модель ``Deal``).
• Удалён неиспользуемый импорт DealStatus.
• Типизация и мелкие правки PEP 8.
"""
import logging
from datetime import datetime

from peewee import fn  # если ещё не импортирован

from database.db import db
from database.models import Client  # обязательно!
from database.models import Deal, Policy, Task
from services.client_service import get_client_by_id
from services.folder_utils import create_deal_folder
from services.task_service import add_task

logger = logging.getLogger(__name__)

# ──────────────────────────── Получение ─────────────────────────────

def get_all_deals():
    """Возвращает все сделки, кроме помеченных как удалённые."""
    return Deal.select().where(Deal.is_deleted == False)


def get_open_deals():
    """Открытые (не закрытые) сделки, не помеченные как удалённые."""
    return Deal.select().where(
        (Deal.is_closed == False) & (Deal.is_deleted == False)
    )


def get_deals_by_client_id(client_id: int):
    return Deal.select().where(
        (Deal.client_id == client_id) & (Deal.is_deleted == False)
    )


def get_deal_by_id(deal_id: int) -> Deal | None:
    return Deal.get_or_none((Deal.id == deal_id) & (Deal.is_deleted == False))


# ──────────────────────────── Добавление ─────────────────────────────

def add_deal(**kwargs):
    """Создаёт новую сделку и связанные задачи.

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

    # FK клиент
    clean_data["client"] = client
    clean_data["is_deleted"] = False

    with db.atomic():
        deal: Deal = Deal.create(**clean_data)
        logger.info("✅ Сделка #%s создана: клиент %s — %s", deal.id, client.name, deal.description)


        # ───── создание папки сделки ─────
        local_path, web_link = create_deal_folder(
            client.name,
            deal.description,
            client_drive_link=client.drive_folder_link, 
        )
        logger.info("📁 Папка сделки создана: %s", local_path)
        if web_link:
            logger.info("🔗 Google Drive-ссылка сделки: %s", web_link)
        deal.drive_folder_path = local_path
        deal.drive_folder_link = web_link or ""   # пустая строка, если Drive не создался
        deal.save()
        # базовые задачи по умолчанию
        
        #add_task(title="расчеты", due_date=deal.start_date, deal_id=deal.id)
        #add_task(title="собрать документы", due_date=deal.start_date, deal_id=deal.id)

        return deal


# ──────────────────────────── Обновление ─────────────────────────────

def update_deal(deal: Deal, **kwargs):
    """Обновляет сделку. Если передано ``calculations``,
    новый текст дописывается над старым с отметкой времени.
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

    # calculations
    new_calc: str | None = kwargs.get("calculations")
    # если закрываем сделку — допишем причину в calculations
    if kwargs.get("is_closed") and kwargs.get("closed_reason"):
        reason = kwargs["closed_reason"]
        ts = datetime.now().strftime("%d.%m.%Y %H:%M")
        auto_note = f"[{ts}]: Сделка закрыта. Причина: {reason}"
        new_calc = f"{auto_note}\n{new_calc or ''}".strip()


    # Если нечего обновлять — возвращаем сделку как есть
    if not updates and not new_calc:
        return deal

    # Применяем простые обновления
    for key, value in updates.items():
        setattr(deal, key, value)

    # Аппендим расчёты
    if new_calc:
        ts = datetime.now().strftime("%d.%m.%Y %H:%M")
        old = deal.calculations or ""
        deal.calculations = f"[{ts}]: {new_calc}\n{old}"

    deal.save()
    return deal


# ──────────────────────────── Удаление ─────────────────────────────

def mark_deal_deleted(deal_id: int):
    deal = Deal.get_or_none(Deal.id == deal_id)
    if deal:
        deal.is_deleted = True
        deal.save()
    else:
        logger.warning("❗ Сделка с id=%s не найдена для удаления", deal_id)


def apply_deal_filters(query, search_text: str = "", show_deleted: bool = False):
    if not show_deleted:
        query = query.where(Deal.is_deleted == False)
    if search_text:
        query = query.where(
            (Deal.description.contains(search_text)) |
            (Deal.status.contains(search_text)) |
            (Client.name.contains(search_text)) |
            (Deal.calculations.contains(search_text))
        )
    return query

# ──────────────────────────── Пагинация ─────────────────────────────

    




def get_deals_page(
    page: int,
    per_page: int,
    search_text: str = "",
    show_deleted: bool = False,
    order_by: str = "reminder_date",
    order_dir: str = "asc",
    **filters
):
    query = build_deal_query(**filters)

    query = apply_deal_filters(query, search_text, show_deleted)


    # 👉 Только один order_by
    if order_by and hasattr(Deal, order_by):
        order_field = getattr(Deal, order_by)
        if order_dir == "desc":
            query = query.order_by(order_field.desc())
        else:
            query = query.order_by(order_field.asc())
    else:
        query = query.order_by(Deal.start_date.desc())


    offset = (page - 1) * per_page
    return query.limit(per_page).offset(offset)






def get_open_deals_page(page: int = 1, per_page: int = 50):
    return (
        Deal.select()
        .where((Deal.is_closed == False) & (Deal.is_deleted == False))
        .order_by(Deal.start_date.desc())
        .paginate(page, per_page)
    )


# ──────────────────────────── Связанные сущности ─────────────────────────────

def get_policies_by_deal_id(deal_id: int):
    return Policy.select().where((Policy.deal == deal_id) & (Policy.is_deleted == False))


def get_tasks_by_deal_id(deal_id: int):
    return Task.select().where((Task.deal == deal_id) & (Task.is_deleted == False))



def build_deal_query(search_text: str = "", show_deleted: bool = False, show_closed: bool = False):
    query = Deal.select().join(Client)

    query = apply_deal_filters(query, search_text, show_deleted)

    if not show_closed:
        query = query.where(Deal.is_closed == False)

    return query




def get_next_deal(current_deal):
    if current_deal.reminder_date is None:
        return None

    return (
        get_open_deals()
        .where(
            (Deal.reminder_date > current_deal.reminder_date) |
            ((Deal.reminder_date == current_deal.reminder_date) & (Deal.id > current_deal.id))
        )
        .order_by(Deal.reminder_date.asc(), Deal.id.asc())
        .first()
    )


def get_prev_deal(current_deal):
    if current_deal.reminder_date is None:
        return None

    return (
        get_open_deals()
        .where(
            (Deal.reminder_date < current_deal.reminder_date) |
            ((Deal.reminder_date == current_deal.reminder_date) & (Deal.id < current_deal.id))
        )
        .order_by(Deal.reminder_date.desc(), Deal.id.desc())
        .first()
    )
