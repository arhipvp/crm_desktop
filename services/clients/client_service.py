"""Сервисный модуль для управления клиентами."""

import logging
import re
import urllib.parse
import webbrowser
from datetime import date, datetime
from typing import Any, Sequence
from peewee import Model, ModelSelect, fn

from database.models import Client, Deal, db
from services.folder_utils import (
    create_client_drive_folder,
    rename_client_folder,
    rename_deal_folder,
    rename_policy_folder,
)
from services.validators import normalize_phone, normalize_full_name
from services.query_utils import apply_search_and_filters
from .dto import ClientDTO

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


class ClientMergeError(RuntimeError):
    """Ошибки, возникающие при объединении клиентов."""


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
    order_by: str | Any = "name",
    order_dir: str = "asc",
) -> ModelSelect:
    """Получить страницу клиентов с учётом фильтров."""
    query = build_client_query(
        search_text=search_text,
        show_deleted=show_deleted,
        column_filters=column_filters,
    )
    if not order_by:
        field = Client.name
    elif isinstance(order_by, str):
        field = getattr(Client, order_by, Client.name)
    else:
        field = order_by
    order_func = field.desc if order_dir == "desc" else field.asc
    offset = (page - 1) * per_page
    return query.order_by(order_func()).limit(per_page).offset(offset)


def get_clients_page_dto(
    page: int,
    per_page: int,
    order_by: str | Any = "name",
    order_dir: str = "asc",
    column_filters: dict[str, str] | None = None,
    **filters,
) -> list[ClientDTO]:
    """Получить страницу клиентов в виде DTO."""
    clients = get_clients_page(
        page,
        per_page,
        order_by=order_by,
        order_dir=order_dir,
        column_filters=column_filters,
        **filters,
    )
    return [ClientDTO.from_model(c) for c in clients]


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

        logger.info("✅ Клиент id=%s: %s создан", client.id, client.name)

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


    log_updates: dict[str, Any] = {}
    for key, value in updates.items():
        if isinstance(value, Model):
            log_updates[key] = str(value)
        elif isinstance(value, (date, datetime)):
            log_updates[key] = value.isoformat()
        else:
            log_updates[key] = value

    logger.info("✏️ Обновление клиента id=%s: %s", client.id, log_updates)


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


def merge_clients(
    primary_id: int,
    duplicate_ids: Sequence[int],
    updates: dict | None = None,
) -> Client:
    """Объединить клиентов, перенеся все связанные сущности к основному."""

    if not duplicate_ids:
        raise ClientMergeError("Список дубликатов пуст")

    unique_duplicates = [cid for cid in dict.fromkeys(duplicate_ids)]
    if primary_id in unique_duplicates:
        raise ClientMergeError("Список дубликатов не должен содержать основной id")

    ids_to_fetch = [primary_id, *unique_duplicates]
    clients = Client.select().where(Client.id.in_(ids_to_fetch))
    clients_by_id = {client.id: client for client in clients}
    missing_ids = [cid for cid in ids_to_fetch if cid not in clients_by_id]
    if missing_ids:
        raise ClientMergeError(
            f"Не найдены клиенты с id: {', '.join(map(str, missing_ids))}"
        )

    primary_client = clients_by_id[primary_id]
    duplicates = [clients_by_id[cid] for cid in unique_duplicates]

    with db.atomic():
        logger.info(
            "🔄 Начало объединения клиента id=%s с дубликатами %s",
            primary_client.id,
            ", ".join(str(d.id) for d in duplicates),
        )

        normalized_updates: dict[str, Any] = {}
        is_active_value_present = False
        is_active_value = False
        if updates:
            if "is_active" in updates:
                active_raw = updates["is_active"]
                if active_raw not in (None, ""):
                    is_active_value_present = True
                    is_active_value = bool(active_raw)
            for key, value in updates.items():
                if key == "is_active":
                    continue
                if key not in CLIENT_ALLOWED_FIELDS or value in (None, ""):
                    continue
                if key == "name":
                    value = normalize_full_name(value)
                elif key == "phone":
                    value = normalize_phone(value)
                    _check_duplicate_phone(value, exclude_id=primary_client.id)
                normalized_updates[key] = value

        updates_to_log: dict[str, Any] = {}
        if normalized_updates:
            updates_to_log.update(normalized_updates)
        if is_active_value_present:
            updates_to_log["is_active"] = is_active_value

        if updates_to_log:
            logger.info(
                "✏️ Обновление основного клиента id=%s при объединении: %s",
                primary_client.id,
                updates_to_log,
            )
            for key, value in normalized_updates.items():
                setattr(primary_client, key, value)
            if is_active_value_present:
                primary_client.is_deleted = not is_active_value
            primary_client.save()

        for duplicate in duplicates:
            logger.info(
                "➡️ Перенос данных клиента id=%s → id=%s",
                duplicate.id,
                primary_client.id,
            )
            for deal in duplicate.deals:
                new_path, new_link = rename_deal_folder(
                    duplicate.name,
                    deal.description,
                    primary_client.name,
                    deal.description,
                    deal.drive_folder_link,
                    deal.drive_folder_path,
                )
                deal.client = primary_client
                if new_path and new_path != deal.drive_folder_path:
                    deal.drive_folder_path = new_path
                if new_link and new_link != deal.drive_folder_link:
                    deal.drive_folder_link = new_link
                deal.save()
                logger.info(
                    "📁 Сделка id=%s перенесена к клиенту id=%s",
                    deal.id,
                    primary_client.id,
                )

            for policy in duplicate.policies:
                old_deal_desc = policy.deal.description if policy.deal_id else None
                new_deal_desc = (
                    policy.deal.description if policy.deal_id else None
                )
                new_path, new_link = rename_policy_folder(
                    duplicate.name,
                    policy.policy_number,
                    old_deal_desc,
                    primary_client.name,
                    policy.policy_number,
                    new_deal_desc,
                    policy.drive_folder_link,
                )
                policy.client = primary_client
                if (
                    policy.deal_id
                    and policy.deal.client_id != primary_client.id
                ):
                    policy.deal = Deal.get_by_id(policy.deal_id)
                if new_path and new_path != policy.drive_folder_link:
                    policy.drive_folder_link = new_path
                elif new_link and new_link != policy.drive_folder_link:
                    policy.drive_folder_link = new_link
                policy.save()
                logger.info(
                    "📄 Полис id=%s перенесён к клиенту id=%s",
                    policy.id,
                    primary_client.id,
                )

        notes: list[str] = []
        if primary_client.note:
            notes.append(primary_client.note)
        for duplicate in duplicates:
            if duplicate.note:
                notes.append(duplicate.note)
        combined_note = "\n\n".join(dict.fromkeys(notes)) if notes else None

        primary_updates: dict[str, Any] = {}
        if combined_note and combined_note != primary_client.note:
            primary_updates["note"] = combined_note

        if not primary_client.email:
            for duplicate in duplicates:
                if duplicate.email:
                    primary_updates["email"] = duplicate.email
                    break

        if not primary_client.phone:
            for duplicate in duplicates:
                if duplicate.phone:
                    try:
                        normalized_phone = normalize_phone(duplicate.phone)
                        _check_duplicate_phone(
                            normalized_phone,
                            exclude_id=primary_client.id,
                        )
                    except ValueError:
                        continue
                    primary_updates["phone"] = normalized_phone
                    break

        if primary_updates:
            logger.info(
                "🧩 Обновление полей клиента id=%s после объединения: %s",
                primary_client.id,
                primary_updates,
            )
            for key, value in primary_updates.items():
                setattr(primary_client, key, value)
            primary_client.save()

        for duplicate in duplicates:
            duplicate.is_deleted = True
            duplicate.drive_folder_path = None
            duplicate.drive_folder_link = None
            duplicate.save()
            logger.info(
                "🗑️ Клиент id=%s помечен удалённым после объединения с id=%s",
                duplicate.id,
                primary_client.id,
            )

        logger.info(
            "✅ Завершено объединение клиента id=%s",
            primary_client.id,
        )

    return primary_client




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
        logger.info("🗑️ Клиент id=%s: %s помечен удалённым", client.id, client.name)
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
    logger.info("🗑️ Помечено удалёнными клиентов: %s", count)
    return count


def delete_clients(clients: list[ClientDTO]) -> None:
    """Удаляет клиентов, переданных в виде DTO."""
    ids = [c.id for c in clients]
    if not ids:
        return
    with db.atomic():
        if len(ids) == 1:
            mark_client_deleted(ids[0])
        else:
            mark_clients_deleted(ids)


def restore_client(client_id: int):
    """Снимает пометку удаления с клиента."""
    client = Client.get_or_none(Client.id == client_id)
    if client:
        client.is_deleted = False
        client.save()
        logger.info("✅ Клиент id=%s восстановлен", client_id)
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
    search_text: str = "",
    show_deleted: bool = False,
    column_filters: dict[str, str] | None = None,
    order_by: str | Any | None = None,
    order_dir: str = "asc",
    **kwargs,
):
    """Создаёт выборку клиентов с учётом фильтров и сортировки."""
    query = Client.active() if not show_deleted else Client.select()
    query = apply_search_and_filters(query, Client, search_text, column_filters)
    if order_by:
        if isinstance(order_by, str):
            field = getattr(Client, order_by, Client.name)
        else:
            field = order_by
        order_func = field.desc if order_dir == "desc" else field.asc
        query = query.order_by(order_func())
    return query
