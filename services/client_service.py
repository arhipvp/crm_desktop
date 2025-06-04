import logging
import re
import urllib.parse
import webbrowser

from database.models import Client, db
from services.folder_utils import (create_client_drive_folder,
                                   rename_client_folder)
from ui.common.validators import normalize_phone

logger = logging.getLogger(__name__)

CLIENT_ALLOWED_FIELDS = {"name", "phone", "email", "is_company", "note"}





# ──────────────────────────── Получение ─────────────────────────────

def get_all_clients():
    return Client.select().where(Client.is_deleted == False)


def get_client_by_id(client_id: int):
    return Client.get_or_none((Client.id == client_id) & (Client.is_deleted == False))


def get_clients_page(page: int, per_page: int, search_text: str = "", show_deleted: bool = False):
    query = Client.select()
    query = apply_client_filters(query, search_text, show_deleted)


    offset = (page - 1) * per_page
    return query.order_by(Client.name.asc()).limit(per_page).offset(offset)




# ──────────────────────────── Добавление ─────────────────────────────

def add_client(**kwargs):
    allowed_fields = CLIENT_ALLOWED_FIELDS


    clean_data = {
        key: kwargs[key]
        for key in allowed_fields
        if key in kwargs and kwargs[key] not in ("", None)
    }

    name = clean_data.get("name")
    if not name:
        logger.warning("❌ Попытка создать клиента без имени")
        raise ValueError("Поле 'name' обязательно для клиента")


    # нормализуем телефон, если он пришёл
    if "phone" in clean_data:
        try:
            clean_data["phone"] = normalize_phone(clean_data["phone"])
        except ValueError as e:
            logger.warning("⚠️ Ошибка нормализации телефона '%s': %s", clean_data["phone"], e)
            raise


    clean_data["is_deleted"] = False

    with db.atomic():
        client, created = Client.get_or_create(name=name, defaults=clean_data)

        try:
            folder_path, folder_link = create_client_drive_folder(name)
            client.drive_folder_path = folder_path
            client.drive_folder_link = folder_link
            client.save()
        except Exception as e:
            logger.error("❌ Ошибка создания папки в Drive: %s", e)


        return client


# ──────────────────────────── Обновление ─────────────────────────────



def update_client(client: Client, **kwargs) -> Client:
    """Обновляет клиента и, при смене ФИО, переименовывает его папку."""

    allowed = CLIENT_ALLOWED_FIELDS

    updates = {
        k: v for k, v in kwargs.items()
        if k in allowed and v not in ("", None)
    }

    # нормализуем телефон
    if "phone" in updates:
        updates["phone"] = normalize_phone(updates["phone"])

    # если нечего менять — сразу выходим
    if not updates:
        return client
    logger.info("✏️ Обновление клиента #%s: %s", client.id, updates)


    # --- переименование папки клиента ---
    old_name = client.name
    new_name = updates.get("name", old_name)

    # применяем обновления к объекту
    for k, v in updates.items():
        setattr(client, k, v)

    # сохраняем все поля разом
    client.save()

    # если имя изменилось — переименовываем папку
    if old_name != new_name:
        new_path, new_link = rename_client_folder(old_name, new_name, client.drive_folder_link)

        if new_path and new_path != client.drive_folder_path:
            client.drive_folder_path = new_path
            logger.info("📁 Обновлён локальный путь клиента: %s", new_path)

        if new_link and new_link != client.drive_folder_link:
            client.drive_folder_link = new_link
            logger.info("🔗 Обновлена ссылка на Google Drive: %s", new_link)

        client.save(update_fields=["drive_folder_path", "drive_folder_link"])

    return client
def apply_client_filters(query, search_text, show_deleted):
    if not show_deleted:
        query = query.where(Client.is_deleted == False)
    if search_text:
        query = query.where(
            (Client.name.contains(search_text)) |
            (Client.phone.contains(search_text)) |
            (Client.email.contains(search_text)) |
            (Client.note.contains(search_text))
        )
    return query


# ──────────────────────────── Удаление ─────────────────────────────

def mark_client_deleted(client_id: int):
    client = Client.get_or_none(Client.id == client_id)
    if client:
        client.is_deleted = True
        client.save()
    else:
        logger.warning("❗ Клиент с id=%s не найден для удаления", client_id)


# ─────────────────────── WhatsApp интеграция ─────────────────────────

def format_phone_for_whatsapp(phone: str) -> str:
    return normalize_phone(phone)



def open_whatsapp(phone: str, message: str | None = None) -> None:
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        raise ValueError("Некорректный номер телефона")

    url = f"https://wa.me/{digits}"
    if message:
        url += "?text=" + urllib.parse.quote(message)

    webbrowser.open(url)


def build_client_query(search_text: str = "", show_deleted: bool = False):
    query = Client.select()
    query = apply_client_filters(query, search_text, show_deleted)

    return query

