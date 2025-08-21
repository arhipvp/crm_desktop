"""Сервисный модуль для управления клиентами."""

import logging
import re
import urllib.parse
import webbrowser
from peewee import ModelSelect, fn

from database.models import Client, Deal, db
from services.folder_utils import create_client_drive_folder, rename_client_folder
from services.validators import normalize_phone, normalize_full_name

logger = logging.getLogger(__name__)

CLIENT_ALLOWED_FIELDS = {"name", "phone", "email", "is_company", "note"}


class DuplicatePhoneError(ValueError):
    """Raised when trying to use a phone that already exists."""

    def __init__(self, phone: str, existing: Client):
        super().__init__(
            f"Телефон {phone} уже указан у клиента '{existing.name}'"
        )
        self.phone = phone
        self.existing = existing


# ──────────────────────────── Получение ─────────────────────────────


def get_all_clients() -> ModelSelect:
    """Вернуть выборку всех активных клиентов."""
    return Client.active()


def get_client_by_id(client_id: int) -> Client | None:
    """Получить клиента по его идентификатору."""
    return Client.active().where(Client.id == client_id).get_or_none()


def get_client_by_phone(phone: str) -> Client | None:
    """Найти клиента по номеру телефона."""
    try:
        phone = normalize_phone(phone)
    except ValueError:
        return None
    return Client.active().where(Client.phone == phone).get_or_none()


def get_clients_page(
    page: int,
    per_page: int,
    search_text: str = "",
    show_deleted: bool = False,
    column_filters: dict[str, str] | None = None,
) -> ModelSelect:
    """Получить страницу клиентов с учётом фильтров."""
    query = Client.active() if not show_deleted else Client.select()
    query = apply_client_filters(query, search_text, column_filters)

    offset = (page - 1) * per_page
    return query.order_by(Client.name.asc()).limit(per_page).offset(offset)


def find_similar_clients(name: str) -> list[Client]:
    """Найти активных клиентов с совпадающим именем.

    Поиск ведётся по полному совпадению нормализованного имени
    либо по совпадению первых двух компонентов (обычно фамилия + имя).
    """

    norm = normalize_full_name(name).lower()
    tokens = norm.split()
    search_first_two = " ".join(tokens[:2]) if tokens else ""

    lc_name = fn.LOWER(Client.name)
    condition = lc_name == norm
    if search_first_two:
        condition |= lc_name.startswith(f"{search_first_two} ")
        condition |= lc_name == search_first_two

    query = Client.active().where(condition)
    return list(query)


def _check_duplicate_phone(phone: str, *, exclude_id: int | None = None) -> None:
    if not phone:
        return
    query = Client.active().where(Client.phone == phone)
    if exclude_id is not None:
        query = query.where(Client.id != exclude_id)
    existing = query.get_or_none()
    if existing:
        raise DuplicatePhoneError(phone, existing)


# ──────────────────────────── Добавление ─────────────────────────────


def add_client(**kwargs) -> Client:
    """Создать и вернуть нового клиента."""
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
    name = normalize_full_name(name)
    clean_data["name"] = name

    if "phone" in clean_data:
        try:
            clean_data["phone"] = normalize_phone(clean_data["phone"])
            _check_duplicate_phone(clean_data["phone"])
        except ValueError as e:
            logger.warning("⚠️ Ошибка нормализации телефона '%s': %s", clean_data["phone"], e)
            raise

    with db.atomic():
        client, _ = Client.get_or_create(name=name, defaults=clean_data)

        try:
            folder_path, folder_link = create_client_drive_folder(name)
            client.drive_folder_path = folder_path
            client.drive_folder_link = folder_link
            client.save()
        except PermissionError as e:
            logger.error(
                "❌ Недостаточно прав для создания папки клиента: %s", e
            )
        except OSError as e:
            logger.error("❌ Ошибка создания папки клиента: %s", e)
        except Exception:
            logger.exception(
                "❌ Неожиданная ошибка при создании папки клиента"
            )
            raise

        return client


# ──────────────────────────── Обновление ─────────────────────────────


def update_client(client: Client, **kwargs) -> Client:
    """Обновить данные клиента и переименовать папку при смене имени."""
    updates = {k: v for k, v in kwargs.items() if k in CLIENT_ALLOWED_FIELDS and v not in ("", None)}

    if "name" in updates:
        updates["name"] = normalize_full_name(updates["name"])
    if "phone" in updates:
        updates["phone"] = normalize_phone(updates["phone"])
        _check_duplicate_phone(updates["phone"], exclude_id=client.id)

    if not updates:
        return client

    logger.info("✏️ Обновление клиента #%s: %s", client.id, updates)

    old_name = client.name
    new_name = updates.get("name", old_name)

    for k, v in updates.items():
        setattr(client, k, v)
    client.save()

    if old_name != new_name:
        new_path, new_link = rename_client_folder(
            old_name, new_name, client.drive_folder_link
        )
        if new_path and new_path != client.drive_folder_path:
            client.drive_folder_path = new_path
            logger.info("📁 Обновлён локальный путь клиента: %s", new_path)
        if new_link and new_link != client.drive_folder_link:
            client.drive_folder_link = new_link
            logger.info("🔗 Обновлена ссылка на Google Drive: %s", new_link)
        client.save(only=[Client.drive_folder_path, Client.drive_folder_link])

        # переименовываем папки всех сделок клиента
        try:
            from services.folder_utils import rename_deal_folder

            for deal in client.deals:
                new_deal_path, _ = rename_deal_folder(
                    old_name,
                    deal.description,
                    new_name,
                    deal.description,
                    deal.drive_folder_link,
                    deal.drive_folder_path,
                )
                if new_deal_path and new_deal_path != deal.drive_folder_path:
                    deal.drive_folder_path = new_deal_path
                    deal.save(only=[Deal.drive_folder_path])
        except Exception:
            logger.exception(
                "Не удалось переименовать папки сделок при смене имени клиента"
            )

    return client


def apply_client_filters(
    query: ModelSelect,
    search_text: str,
    column_filters: dict[str, str] | None = None,
) -> ModelSelect:
    """Применяет фильтры поиска к выборке клиентов."""
    if search_text:
        query = query.where(
            (Client.name.contains(search_text))
            | (Client.phone.contains(search_text))
            | (Client.email.contains(search_text))
            | (Client.note.contains(search_text))
        )
    from services.query_utils import apply_column_filters

    query = apply_column_filters(query, column_filters, Client)
    return query


# ──────────────────────────── Удаление ─────────────────────────────


def mark_client_deleted(client_id: int):
    """Помечает клиента как удалённого."""
    client = Client.get_or_none(Client.id == client_id)
    if client:
        client.soft_delete()
        try:
            from services.folder_utils import rename_client_folder

            new_name = f"{client.name} deleted"
            new_path, new_link = rename_client_folder(
                client.name, new_name, client.drive_folder_link
            )
            client.name = new_name
            client.drive_folder_path = new_path
            if new_link:
                client.drive_folder_link = new_link
            client.save(
                only=[Client.name, Client.drive_folder_path, Client.drive_folder_link, Client.is_deleted]
            )
        except Exception:
            logger.exception("Не удалось пометить папку клиента удалённой")
    else:
        logger.warning("❗ Клиент с id=%s не найден для удаления", client_id)


def mark_clients_deleted(client_ids: list[int]) -> int:
    """Массово помечает клиентов удалёнными."""
    if not client_ids:
        return 0

    count = 0
    for cid in client_ids:
        before = Client.get_or_none(Client.id == cid)
        if before and not before.is_deleted:
            mark_client_deleted(cid)
            count += 1

    return count


def restore_client(client_id: int):
    """Снимает пометку удаления с клиента."""
    client = Client.get_or_none(Client.id == client_id)
    if client:
        client.is_deleted = False
        client.save()
        logger.info("✅ Клиент %s восстановлен", client_id)
    else:
        logger.warning("❗ Клиент с id=%s не найден для восстановления", client_id)


# ─────────────────────── WhatsApp интеграция ─────────────────────────


def format_phone_for_whatsapp(phone: str) -> str:
    """Возвращает номер телефона в формате, пригодном для WhatsApp."""
    return normalize_phone(phone)


def open_whatsapp(phone: str, message: str | None = None) -> None:
    """Открывает чат WhatsApp в браузере с необязательным сообщением."""
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        raise ValueError("Некорректный номер телефона")

    url = f"https://wa.me/{digits}"
    if message:
        url += "?text=" + urllib.parse.quote(message)

    webbrowser.open(url)


def build_client_query(
    search_text: str = "", show_deleted: bool = False, column_filters: dict[str, str] | None = None
):
    """Создаёт выборку клиентов с учётом фильтров."""
    query = Client.active() if not show_deleted else Client.select()
    return apply_client_filters(query, search_text, column_filters)
