"""Утилиты для работы с локальными папками и Google Drive."""

from __future__ import annotations

import logging
# services/folder_utils.py
import os
import re
import subprocess
import sys
import webbrowser
from functools import lru_cache
from typing import Optional, Tuple

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except Exception:  # noqa: BLE001
    Credentials = None  # type: ignore[assignment]
    build = lambda *a, **k: None  # type: ignore[assignment]
    MediaFileUpload = None  # type: ignore[assignment]

try:
    from PySide6.QtWidgets import QApplication, QMessageBox
except Exception:  # PySide6 может отсутствовать в тестах
    QApplication = None  # type: ignore[assignment]
    QMessageBox = None

logger = logging.getLogger(__name__)

SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_CREDENTIALS", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/drive"]
ROOT_FOLDER_ID = "1-hTRZ7meDTGDQezoY_ydFkmXIng3gXFm"  # ID папки в Google Drive
GOOGLE_DRIVE_LOCAL_ROOT = os.getenv("GOOGLE_DRIVE_LOCAL_ROOT", r"G:\Мой диск\Клиенты")




@lru_cache(maxsize=1)
def get_drive_service():
    """Создать и закешировать сервис Google Drive.

    Returns:
        Resource: Клиент API Google Drive.
    """
    if Credentials is None:
        raise RuntimeError("Google Drive libraries are not available")
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)

def sanitize_name(name: str) -> str:
    """
    Очищает имя от недопустимых символов для файловой системы:
    Заменяет символы: < > : "  и пробельные/невидимые.
    """
    import re
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', '_', name)  # заменяем все опасные символы
    name = re.sub(r'\s{2,}', ' ', name).strip()      # схлопываем пробелы
    return name.rstrip(' .')                         # убираем завершающие пробелы/точки


def extract_folder_id(link: str) -> str:
    if not link:
        return None
    return link.rstrip("/").split("/")[-1]

def create_drive_folder(folder_name: str, parent_id: str = ROOT_FOLDER_ID) -> str:
    folder_name = sanitize_name(folder_name)
    service = get_drive_service()

    query = f"'{parent_id}' in parents and name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    response = service.files().list(q=query, fields="files(id)", spaces='drive').execute()
    files = response.get("files", [])

    if files:
        folder_id = files[0]["id"]
        return f"https://drive.google.com/drive/folders/{folder_id}"

    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id]
    }

    folder = service.files().create(body=metadata, fields="id").execute()
    return f"https://drive.google.com/drive/folders/{folder['id']}"

def create_client_drive_folder(client_name: str) -> tuple[str, str]:
    """Создать локальную папку клиента и вернуть (локальный путь, веб-ссылку)."""
    safe_name = sanitize_name(client_name)
    local_path = os.path.join(GOOGLE_DRIVE_LOCAL_ROOT, safe_name)

    try:
        os.makedirs(local_path, exist_ok=True)
    except Exception as e:
        logger.error("❌ Не удалось создать папку полиса: %s", e)

        return None, None

    # Создаём настоящую папку в Google Диске
    web_link = create_drive_folder(safe_name)
    return local_path, web_link


def open_local_or_web(folder_link: str, folder_name: str = None, parent=None):
    logger.debug(">>> [open_local_or_web] folder_link:", folder_link)

    if not folder_link and not folder_name:
        QMessageBox.warning(parent, "Ошибка", "Нет ссылки и нет имени папки.")
        return

    if not folder_name:
        folder_name = "???"  # fallback имя

    client_path = os.path.join(GOOGLE_DRIVE_LOCAL_ROOT, folder_name)
    logger.debug(">>> [search] checking client path: %s", client_path)

    if os.path.isdir(client_path):
        # Если есть локальная папка клиента
        for sub in os.listdir(client_path):
            sub_path = os.path.join(client_path, sub)
            if os.path.isdir(sub_path) and (sub == folder_name or sub.endswith(folder_name)):
                logger.debug(">>> [match] found subfolder: %s", sub_path)
                os.startfile(sub_path)
                return

        # Или просто открыть саму папку клиента
        logger.info(">>> [fallback] opening client root folder: %s", client_path)
        os.startfile(client_path)
        return

    # Если локальной папки нет, но есть web-ссылка
    if folder_link:
        logger.info(">>> [fallback] opening web link: %s", folder_link)
        webbrowser.open(folder_link)
    else:
        QMessageBox.warning(parent, "Ошибка", f"Не удалось найти папку клиента: {folder_name}")



def create_deal_folder(
    client_name: str,
    deal_description: str,
    *,
    client_drive_link: str | None,          # ← ссылка на ПАПКУ КЛИЕНТА
) -> Tuple[str, Optional[str]]:
    """
    Создаёт папку сделки на диске и (если есть client_drive_link)
    подпапку «Сделка - …» в уже существующей папке клиента на Google Drive.

    Returns
    -------
    (local_path, web_link or None)
    """
    # -------- название папки сделки
    deal_name   = sanitize_name(f"Сделка - {deal_description}")

    # -------- локальный путь  G:\…\Клиенты\<Клиент>\Сделка - …
    local_path = os.path.join(
        GOOGLE_DRIVE_LOCAL_ROOT,
        sanitize_name(client_name),
        deal_name,
    )
    os.makedirs(local_path, exist_ok=True)
    logger.info("📂  Создана локальная папка сделки: %s", local_path)

    # -------- облако: только если передали ссылку клиента
    web_link: Optional[str] = None
    if client_drive_link:
        try:
            parent_id = extract_folder_id(client_drive_link)       # ID папки клиента
            web_link  = create_drive_folder(deal_name, parent_id)  # подпапка сделки
            logger.info("☁️  Drive-папка сделки: %s", web_link)
        except Exception:
            logger.exception("Не удалось создать подпапку сделки на Drive")

    return local_path, web_link



def create_policy_folder(client_name: str, policy_number: str, deal_description: str = None) -> str:
    """Создать папку для полиса внутри клиента или сделки."""
    client_name = sanitize_name(client_name)
    policy_name = sanitize_name(f"Полис - {policy_number}")

    if deal_description:
        deal_name = sanitize_name(f"Сделка - {deal_description}")
        path = os.path.join(GOOGLE_DRIVE_LOCAL_ROOT, client_name, deal_name, policy_name)
    else:
        path = os.path.join(GOOGLE_DRIVE_LOCAL_ROOT, client_name, policy_name)

    try:
        os.makedirs(path, exist_ok=True)
        return path
    except Exception as e:
        logger.error("❌ Не удалось создать папку клиента: %s", e)

        return None

def upload_to_drive(local_path: str, drive_folder_id: str) -> str:
    """
    Загружает файл на Google Drive и возвращает ссылку.
    """
    from googleapiclient.http import MediaFileUpload

    service = get_drive_service()  # ← вместо get_gdrive_credentials

    file_metadata = {
        "name": os.path.basename(local_path),
        "parents": [drive_folder_id]
    }
    media = MediaFileUpload(local_path, resumable=True)

    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink"
    ).execute()

    logger.info("☁️ Загружен: %s", uploaded['webViewLink'])
    return uploaded["webViewLink"]

def open_folder(path_or_url: str, *, parent: Optional["QWidget"] = None) -> None:  # noqa: N802 (keep API)
    """Пытается открыть строку как локальный путь, иначе — как URL.

    Parameters
    ----------
    path_or_url: str
        Локальный путь к каталогу **или** web‑ссылка.
    parent: QWidget | None
        Родительский виджет для QMessageBox; может быть None вне Qt.
    """
    if not path_or_url:
        _msg("Папка не задана.", parent)
        return

    path_or_url = path_or_url.strip()

    if os.path.isdir(path_or_url):  # локальный каталог существует
        try:
            if sys.platform.startswith("win"):
                os.startfile(path_or_url)  # type: ignore[attr-defined]
            elif sys.platform.startswith("darwin"):
                subprocess.Popen(["open", path_or_url])
            else:
                subprocess.Popen(["xdg-open", path_or_url])
            return
        except Exception as exc:
            logger.exception("Не удалось открыть каталог %s", path_or_url)
            _msg(f"Не удалось открыть каталог:\n{exc}", parent)
            return

    # иначе трактуем как URL
    webbrowser.open(path_or_url)

def _msg(text: str, parent: Optional["QWidget"]) -> None:
    """Показывает информационное QMessageBox, если Qt доступен."""
    if QMessageBox is None or QApplication is None or QApplication.instance() is None:
        logger.info("MSG: %s", text)
        return
    QMessageBox.information(parent, "Информация", text)


def rename_client_folder(old_name: str, new_name: str, drive_link: str | None):
    """Переименовывает папку клиента локально и на Google Drive.

    Возвращает кортеж:
        (новый_локальный_путь, актуальная_web-ссылка_или_None)
    """
    # 1) локальный диск -------------------------------------------------
    old_path = os.path.join(GOOGLE_DRIVE_LOCAL_ROOT, old_name)
    new_path = os.path.join(GOOGLE_DRIVE_LOCAL_ROOT, new_name)

    try:
        if os.path.isdir(old_path):
            # если уже есть new_path, значит вручную переименовали — ничего не делаем
            if not os.path.isdir(new_path):
                os.rename(old_path, new_path)
        else:
            # старой папки нет → просто создадим новую (чтобы не упасть)
            os.makedirs(new_path, exist_ok=True)
    except Exception:
        logger.exception("Не удалось переименовать локальную папку клиента")

    # 2) Google Drive ---------------------------------------------------
    if drive_link:
        try:
            service = get_drive_service()
            file_id = extract_folder_id(drive_link)
            service.files().update(
                fileId=file_id,
                body={"name": new_name},
                fields="id"          # ничего лишнего не запрашиваем
            ).execute()
            # ссылка вида .../folders/<id> остаётся валидной → можно вернуть как есть
        except Exception:
            logger.exception("Не удалось переименовать папку клиента на Drive")

    return new_path, drive_link

