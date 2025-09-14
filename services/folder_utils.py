"""Утилиты для работы с локальными папками и Google Drive."""

from __future__ import annotations

import logging

# services/folder_utils.py
import os
from os import getenv
import re
import shutil
import subprocess
import sys
import webbrowser
from functools import lru_cache
import time
from pathlib import Path
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

SERVICE_ACCOUNT_FILE = getenv("GOOGLE_CREDENTIALS", "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/drive"]
ROOT_FOLDER_ID = getenv(
    "GOOGLE_ROOT_FOLDER_ID", "1-hTRZ7meDTGDQezoY_ydFkmXIng3gXFm"
)  # ID папки в Google Drive
GOOGLE_DRIVE_LOCAL_ROOT = Path(
    getenv("GOOGLE_DRIVE_LOCAL_ROOT", r"G:\Мой диск\Клиенты")
)


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
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', "_", name)  # заменяем все опасные символы
    name = re.sub(r"\s{2,}", " ", name).strip()  # схлопываем пробелы
    return name.rstrip(" .")  # убираем завершающие пробелы/точки


def extract_folder_id(link: str | None) -> str | None:
    """Извлечь идентификатор папки из ссылки Google Drive."""

    if not link:
        return None

    return link.rstrip("/").split("/")[-1]


def create_drive_folder(folder_name: str, parent_id: str = ROOT_FOLDER_ID) -> str:
    folder_name = sanitize_name(folder_name)
    service = get_drive_service()

    query = f"'{parent_id}' in parents and name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    response = (
        service.files().list(q=query, fields="files(id)", spaces="drive").execute()
    )
    files = response.get("files", [])

    if files:
        folder_id = files[0]["id"]
        return f"https://drive.google.com/drive/folders/{folder_id}"

    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }

    folder = service.files().create(body=metadata, fields="id").execute()
    return f"https://drive.google.com/drive/folders/{folder['id']}"


def find_drive_folder(folder_name: str, parent_id: str = ROOT_FOLDER_ID) -> str | None:
    """Найти существующую папку в Google Drive и вернуть webViewLink."""
    folder_name = sanitize_name(folder_name)
    service = get_drive_service()

    query = (
        f"'{parent_id}' in parents and name = '{folder_name}' and "
        "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    response = (
        service.files()
        .list(q=query, fields="files(id, webViewLink)", spaces="drive")
        .execute()
    )
    files = response.get("files", [])
    if files:
        return files[0].get("webViewLink")
    return None


def create_client_drive_folder(client_name: str) -> Tuple[str, Optional[str]]:
    """Создать локальную папку клиента и вернуть её путь.

    Папка на Google Drive больше не создаётся автоматически. ``web_link``
    всегда будет ``None``.
    """
    safe_name = sanitize_name(client_name)
    local_path = GOOGLE_DRIVE_LOCAL_ROOT / safe_name

    try:
        local_path.mkdir(parents=True, exist_ok=True)
        logger.info("📁 Создана папка клиента: %s", local_path)
    except Exception:
        logger.exception("Не удалось создать папку клиента локально")

    return str(local_path), None


def open_local_or_web(folder_link: str, folder_name: str = None, parent=None):
    logger.debug(">>> [open_local_or_web] folder_link: %s", folder_link)

    if not folder_link and not folder_name:
        QMessageBox.warning(parent, "Ошибка", "Нет ссылки и нет имени папки.")
        return

    if not folder_name:
        folder_name = "???"  # fallback имя

    client_path = GOOGLE_DRIVE_LOCAL_ROOT / folder_name
    logger.debug(">>> [search] checking client path: %s", client_path)

    if client_path.is_dir():
        # Если есть локальная папка клиента
        for sub_path in client_path.iterdir():
            if sub_path.is_dir() and (
                sub_path.name == folder_name or sub_path.name.endswith(folder_name)
            ):
                logger.debug(">>> [match] found subfolder: %s", sub_path)
                open_folder(str(sub_path), parent=parent)
                return

        # Или просто открыть саму папку клиента
        logger.debug(">>> [fallback] opening client root folder: %s", client_path)
        open_folder(str(client_path), parent=parent)
        return

    # Локальной папки нет
    if QApplication is not None and QMessageBox is not None and QApplication.instance():
        res = QMessageBox.question(
            parent,
            "Папка не найдена",
            "Не удалось найти локальную папку. Привязать путь вручную?",
            QMessageBox.Yes | QMessageBox.Cancel,
        )
        if res == QMessageBox.Yes:
            try:
                from PySide6.QtWidgets import QFileDialog

                chosen = QFileDialog.getExistingDirectory(parent, "Укажите папку клиента")
                if chosen:
                    open_folder(chosen, parent=parent)
            except Exception:
                logger.exception("Ошибка выбора папки")
        return

    # Нет GUI или пользователь отменил → открываем ссылку, если есть
    if folder_link:
        logger.debug(">>> [fallback] opening web link: %s", folder_link)
        webbrowser.open(folder_link)
    else:
        if QMessageBox is not None:
            QMessageBox.warning(
                parent, "Ошибка", f"Не удалось найти папку клиента: {folder_name}"
            )
        else:
            logger.warning("Не удалось найти папку клиента: %s", folder_name)


def create_deal_folder(
    client_name: str,
    deal_description: str,
    *,
    client_drive_link: str | None,  # ← ссылка на ПАПКУ КЛИЕНТА
) -> Tuple[str, Optional[str]]:
    """Создать папку сделки только локально.

    Папка на Google Drive больше не создаётся автоматически.

    Returns
    -------
    Tuple[str, Optional[str]]
        Путь к созданной локальной папке и ``None`` вместо ссылки.
    """
    # -------- название папки сделки
    deal_name = sanitize_name(f"Сделка - {deal_description}")

    # -------- локальный путь  G:\…\Клиенты\<Клиент>\Сделка - …
    local_path = (
        GOOGLE_DRIVE_LOCAL_ROOT
        / sanitize_name(client_name)
        / deal_name
    )

    logger.info("📂  Ожидаемый путь сделки: %s", local_path)

    # -------- создаём локальную папку (как у полиса)
    if local_path.is_dir():
        logger.info("📂 Папка сделки уже существует: %s", local_path)
    else:
        _msg(f"Папка сделки не найдена и будет создана:\n{local_path}", None)
        try:
            local_path.mkdir(parents=True, exist_ok=True)
            logger.info("📁 Создана папка сделки: %s", local_path)
        except Exception:
            logger.exception("Не удалось создать папку сделки локально")

    # -------- облако более не создаётся автоматически
    return str(local_path), None


def create_policy_folder(
    client_name: str, policy_number: str, deal_description: str = None
) -> str:
    """Создать папку для полиса внутри клиента или сделки."""
    client_name = sanitize_name(client_name)
    policy_name = sanitize_name(f"Полис - {policy_number}")

    if deal_description:
        deal_name = sanitize_name(f"Сделка - {deal_description}")
        path = (
            GOOGLE_DRIVE_LOCAL_ROOT / client_name / deal_name / policy_name
        )
    else:
        path = GOOGLE_DRIVE_LOCAL_ROOT / client_name / policy_name

    try:
        path.mkdir(parents=True, exist_ok=True)
        return str(path)
    except Exception as e:
        logger.error("❌ Не удалось создать папку клиента: %s", e)

        return None


def upload_to_drive(local_path: str, drive_folder_id: str) -> str:
    """
    Загружает файл на Google Drive и возвращает ссылку.
    """
    from googleapiclient.http import MediaFileUpload

    service = get_drive_service()  # ← вместо get_gdrive_credentials

    file_metadata = {"name": Path(local_path).name, "parents": [drive_folder_id]}
    media = MediaFileUpload(str(local_path), resumable=True)

    uploaded = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id, webViewLink")
        .execute()
    )

    logger.info("☁️ Загружен: %s", uploaded["webViewLink"])
    return uploaded["webViewLink"]


def open_folder(
    path_or_url: str, *, parent: Optional["QWidget"] = None
) -> None:  # noqa: N802 (keep API)
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
    path = Path(path_or_url)

    if path.is_dir():  # локальный каталог существует
        try:
            if sys.platform.startswith("win"):
                try:
                    import win32com.client  # type: ignore[import-not-found]

                    shell = win32com.client.Dispatch("Shell.Application")
                    target = str(path.resolve()).casefold()
                    for window in shell.Windows():
                        try:
                            current = str(
                                Path(window.Document.Folder.Self.Path).resolve()
                            ).casefold()
                            if current == target:
                                window.Visible = True
                                try:
                                    window.Focus()  # type: ignore[attr-defined]
                                except Exception:
                                    pass
                                return
                        except Exception:
                            continue
                    shell.Open(str(path))
                except Exception:
                    os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform.startswith("darwin"):
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
            return
        except Exception as exc:
            logger.exception("Не удалось открыть каталог %s", path)
            _msg(f"Не удалось открыть каталог:\n{exc}", parent)
            return

    # иначе трактуем как URL
    webbrowser.open(path_or_url)


def copy_path_to_clipboard(
    path_or_url: str, *, parent: Optional["QWidget"] = None
) -> None:
    """Копировать путь или ссылку в буфер обмена."""
    if not path_or_url:
        _msg("Папка не задана.", parent)
        return

    path_or_url = path_or_url.strip()

    try:
        from PySide6.QtGui import QGuiApplication
    except Exception:  # PySide6 может отсутствовать в тестах
        logger.info("Clipboard not available")
        return

    if QGuiApplication.instance() is None:
        logger.info("No GUI application for clipboard")
        return

    QGuiApplication.clipboard().setText(path_or_url)
    _msg("Путь скопирован в буфер обмена.", parent)


def copy_text_to_clipboard(text: str, *, parent: Optional["QWidget"] = None) -> None:
    """Копирует произвольный текст в буфер обмена."""
    if not text:
        _msg("Пустой текст.", parent)
        return

    try:
        from PySide6.QtGui import QGuiApplication
    except Exception:  # может отсутствовать в тестах
        logger.info("Clipboard not available")
        return

    if QGuiApplication.instance() is None:
        logger.info("No GUI application for clipboard")
        return

    QGuiApplication.clipboard().setText(text)
    _msg("Текст скопирован в буфер обмена.", parent)


def _msg(text: str, parent: Optional["QWidget"]) -> None:
    """Показывает информационное QMessageBox, если Qt доступен."""
    if QMessageBox is None or QApplication is None or QApplication.instance() is None:
        logger.debug("MSG: %s", text)
        return
    QMessageBox.information(parent, "Информация", text)


def rename_client_folder(old_name: str, new_name: str, drive_link: str | None):
    """Переименовывает папку клиента локально и на Google Drive.

    Возвращает кортеж:
        (новый_локальный_путь, актуальная_web-ссылка_или_None)
    """
    # 1) локальный диск -------------------------------------------------
    old_path = GOOGLE_DRIVE_LOCAL_ROOT / old_name
    new_path = GOOGLE_DRIVE_LOCAL_ROOT / new_name

    try:
        if old_path.is_dir():
            # если уже есть new_path, значит вручную переименовали — ничего не делаем
            if not new_path.is_dir():
                old_path.rename(new_path)
        else:
            # старой папки нет → просто создадим новую (чтобы не упасть)
            new_path.mkdir(parents=True, exist_ok=True)
    except Exception:
        logger.exception("Не удалось переименовать локальную папку клиента")

    # 2) Google Drive ---------------------------------------------------
    if drive_link:
        try:
            service = get_drive_service()
            file_id = extract_folder_id(drive_link)
            if file_id:
                service.files().update(
                    fileId=file_id,
                    body={"name": new_name},
                    fields="id",  # ничего лишнего не запрашиваем
                ).execute()
            # ссылка вида .../folders/<id> остаётся валидной → можно вернуть как есть
        except Exception:
            logger.exception("Не удалось переименовать папку клиента на Drive")

    return str(new_path), drive_link


def rename_deal_folder(
    old_client_name: str,
    old_description: str,
    new_client_name: str,
    new_description: str,
    drive_link: str | None,
    current_path: str | None = None,
):
    """Переименовать или переместить папку сделки."""

    default_old_path = (
        GOOGLE_DRIVE_LOCAL_ROOT
        / sanitize_name(old_client_name)
        / sanitize_name(f"Сделка - {old_description}")
    )
    # если передан фактический путь и он существует — используем его
    old_path = (
        Path(current_path)
        if current_path and Path(current_path).is_dir()
        else default_old_path
    )
    new_path = (
        GOOGLE_DRIVE_LOCAL_ROOT
        / sanitize_name(new_client_name)
        / sanitize_name(f"Сделка - {new_description}")
    )

    try:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        if old_path.is_dir():
            if not new_path.is_dir():
                old_path.rename(new_path)
                logger.info("📂 Папка сделки перемещена: %s → %s", old_path, new_path)
            else:
                logger.info("📂 Папка сделки уже в нужном месте: %s", new_path)
        elif new_path.is_dir():
            # папка уже в нужном месте (например, переименовали родителя)
            logger.info("📂 Папка сделки уже в нужном месте: %s", new_path)
        else:
            _msg(f"Папка сделки не найдена: {old_path}\nСоздаю новую.", None)
            new_path.mkdir(parents=True, exist_ok=True)
            logger.info("📁 Создана новая папка сделки: %s", new_path)
    except Exception:
        logger.exception("Не удалось переименовать локальную папку сделки")

    if drive_link:
        try:
            service = get_drive_service()
            file_id = extract_folder_id(drive_link)
            if file_id:
                service.files().update(
                    fileId=file_id,
                    body={"name": sanitize_name(f"Сделка - {new_description}")},
                    fields="id",
                ).execute()
        except Exception:
            logger.exception("Не удалось переименовать папку сделки на Drive")

    return new_path, drive_link


def rename_policy_folder(
    old_client_name: str,
    old_policy_number: str,
    old_deal_desc: str | None,
    new_client_name: str,
    new_policy_number: str,
    new_deal_desc: str | None,
    drive_link: str | None,
):
    """Переименовать папку полиса."""

    old_path = GOOGLE_DRIVE_LOCAL_ROOT / sanitize_name(old_client_name)
    if old_deal_desc:
        old_path /= sanitize_name(f"Сделка - {old_deal_desc}")
    old_path /= sanitize_name(f"Полис - {old_policy_number}")

    new_path = GOOGLE_DRIVE_LOCAL_ROOT / sanitize_name(new_client_name)
    if new_deal_desc:
        new_path /= sanitize_name(f"Сделка - {new_deal_desc}")
    new_path /= sanitize_name(f"Полис - {new_policy_number}")

    try:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        if old_path.is_dir():
            if not new_path.is_dir():
                old_path.rename(new_path)
        else:
            new_path.mkdir(parents=True, exist_ok=True)
    except Exception:
        logger.exception("Не удалось переименовать локальную папку полиса")

    if drive_link:
        try:
            service = get_drive_service()
            file_id = extract_folder_id(drive_link)
            if file_id:
                service.files().update(
                    fileId=file_id,
                    body={"name": sanitize_name(f"Полис - {new_policy_number}")},
                    fields="id",
                ).execute()
        except Exception:
            logger.exception("Не удалось переименовать папку полиса на Drive")

    return str(new_path), drive_link


def move_policy_folder_to_deal(
    policy_path: str | None,
    client_name: str,
    deal_description: str,
) -> str | None:
    """Переместить папку полиса в папку сделки.

    Parameters
    ----------
    policy_path: str | None
        Текущий путь к папке полиса.
    client_name: str
        Имя клиента для формирования иерархии.
    deal_description: str
        Описание сделки.

    Returns
    -------
    str | None
        Новый путь к папке или ``None`` при ошибке.
    """

    if not policy_path:
        return None

    policy_name = Path(policy_path).name
    client_name = sanitize_name(client_name)
    deal_name = sanitize_name(f"Сделка - {deal_description}")
    dest_dir = GOOGLE_DRIVE_LOCAL_ROOT / client_name / deal_name
    dest_dir.mkdir(parents=True, exist_ok=True)
    new_path = dest_dir / policy_name

    try:
        shutil.move(policy_path, new_path)
        logger.info("📁 Папка полиса перемещена: %s", new_path)
    except Exception:
        logger.exception("Не удалось переместить папку полиса")
        return None

    return str(new_path)


def move_file_to_folder(file_path: str, folder_path: str) -> str | None:
    """Переместить файл в указанную папку.

    Parameters
    ----------
    file_path: str
        Исходный путь к файлу.
    folder_path: str
        Назначение, куда переместить файл.

    Returns
    -------
    str | None
        Новый путь файла или ``None`` при ошибке.
    """

    if not file_path or not Path(file_path).is_file():
        return None

    folder = Path(folder_path)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / Path(file_path).name

    try:
        shutil.move(file_path, dest)
        logger.info("📄 Файл полиса перемещён: %s", dest)
    except Exception:
        logger.exception("Не удалось переместить файл полиса")
        return None

    return str(dest)
