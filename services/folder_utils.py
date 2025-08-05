"""Утилиты для работы с локальными папками и Google Drive."""

from __future__ import annotations

import logging

# services/folder_utils.py
import os
import re
import shutil
import subprocess
import sys
import webbrowser
from functools import lru_cache
import time
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
ROOT_FOLDER_ID = os.getenv(
    "GOOGLE_ROOT_FOLDER_ID", "1-hTRZ7meDTGDQezoY_ydFkmXIng3gXFm"
)  # ID папки в Google Drive
GOOGLE_DRIVE_LOCAL_ROOT = os.getenv(
    "GOOGLE_DRIVE_LOCAL_ROOT", r"G:\Мой диск\Клиенты"
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
    local_path = os.path.join(GOOGLE_DRIVE_LOCAL_ROOT, safe_name)

    try:
        os.makedirs(local_path, exist_ok=True)
        logger.info("📁 Создана папка клиента: %s", local_path)
    except Exception:
        logger.exception("Не удалось создать папку клиента локально")

    return local_path, None


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
            if os.path.isdir(sub_path) and (
                sub == folder_name or sub.endswith(folder_name)
            ):
                logger.debug(">>> [match] found subfolder: %s", sub_path)
                os.startfile(sub_path)
                return

        # Или просто открыть саму папку клиента
        logger.info(">>> [fallback] opening client root folder: %s", client_path)
        os.startfile(client_path)
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
                    os.startfile(chosen)
            except Exception:
                logger.exception("Ошибка выбора папки")
        return

    # Нет GUI или пользователь отменил → открываем ссылку, если есть
    if folder_link:
        logger.info(">>> [fallback] opening web link: %s", folder_link)
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
    local_path = os.path.join(
        GOOGLE_DRIVE_LOCAL_ROOT,
        sanitize_name(client_name),
        deal_name,
    )

    logger.info("📂  Ожидаемый путь сделки: %s", local_path)

    # -------- создаём локальную папку (как у полиса)
    if os.path.isdir(local_path):
        logger.info("📂 Папка сделки уже существует: %s", local_path)
    else:
        _msg(f"Папка сделки не найдена и будет создана:\n{local_path}", None)
        try:
            os.makedirs(local_path, exist_ok=True)
            logger.info("📁 Создана папка сделки: %s", local_path)
        except Exception:
            logger.exception("Не удалось создать папку сделки локально")

    # -------- облако более не создаётся автоматически
    return local_path, None


def create_policy_folder(
    client_name: str, policy_number: str, deal_description: str = None
) -> str:
    """Создать папку для полиса внутри клиента или сделки."""
    client_name = sanitize_name(client_name)
    policy_name = sanitize_name(f"Полис - {policy_number}")

    if deal_description:
        deal_name = sanitize_name(f"Сделка - {deal_description}")
        path = os.path.join(
            GOOGLE_DRIVE_LOCAL_ROOT, client_name, deal_name, policy_name
        )
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

    file_metadata = {"name": os.path.basename(local_path), "parents": [drive_folder_id]}
    media = MediaFileUpload(local_path, resumable=True)

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

    if os.path.isdir(path_or_url):  # локальный каталог существует
        try:
            if sys.platform.startswith("win"):
                try:
                    import win32com.client  # type: ignore[import-not-found]

                    shell = win32com.client.Dispatch("Shell.Application")
                    target = os.path.normcase(os.path.realpath(path_or_url))
                    for window in shell.Windows():
                        try:
                            current = os.path.normcase(
                                os.path.realpath(window.Document.Folder.Self.Path)
                            )
                            if current == target:
                                window.Visible = True
                                try:
                                    window.Focus()  # type: ignore[attr-defined]
                                except Exception:
                                    pass
                                return
                        except Exception:
                            continue
                    shell.Open(path_or_url)
                except Exception:
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
            if file_id:
                service.files().update(
                    fileId=file_id,
                    body={"name": new_name},
                    fields="id",  # ничего лишнего не запрашиваем
                ).execute()
            # ссылка вида .../folders/<id> остаётся валидной → можно вернуть как есть
        except Exception:
            logger.exception("Не удалось переименовать папку клиента на Drive")

    return new_path, drive_link


def rename_deal_folder(
    old_client_name: str,
    old_description: str,
    new_client_name: str,
    new_description: str,
    drive_link: str | None,
    current_path: str | None = None,
):
    """Переименовать или переместить папку сделки."""

    default_old_path = os.path.join(
        GOOGLE_DRIVE_LOCAL_ROOT,
        sanitize_name(old_client_name),
        sanitize_name(f"Сделка - {old_description}"),
    )
    # если передан фактический путь и он существует — используем его
    old_path = (
        current_path
        if current_path and os.path.isdir(current_path)
        else default_old_path
    )
    new_path = os.path.join(
        GOOGLE_DRIVE_LOCAL_ROOT,
        sanitize_name(new_client_name),
        sanitize_name(f"Сделка - {new_description}"),
    )

    try:
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        if os.path.isdir(old_path):
            if not os.path.isdir(new_path):
                os.rename(old_path, new_path)
                logger.info("📂 Папка сделки перемещена: %s → %s", old_path, new_path)
            else:
                logger.info("📂 Папка сделки уже в нужном месте: %s", new_path)
        elif os.path.isdir(new_path):
            # папка уже в нужном месте (например, переименовали родителя)
            logger.info("📂 Папка сделки уже в нужном месте: %s", new_path)
        else:
            _msg(f"Папка сделки не найдена: {old_path}\nСоздаю новую.", None)
            os.makedirs(new_path, exist_ok=True)
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

    parts_old = [GOOGLE_DRIVE_LOCAL_ROOT, sanitize_name(old_client_name)]
    if old_deal_desc:
        parts_old.append(sanitize_name(f"Сделка - {old_deal_desc}"))
    parts_old.append(sanitize_name(f"Полис - {old_policy_number}"))
    old_path = os.path.join(*parts_old)

    parts_new = [GOOGLE_DRIVE_LOCAL_ROOT, sanitize_name(new_client_name)]
    if new_deal_desc:
        parts_new.append(sanitize_name(f"Сделка - {new_deal_desc}"))
    parts_new.append(sanitize_name(f"Полис - {new_policy_number}"))
    new_path = os.path.join(*parts_new)

    try:
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        if os.path.isdir(old_path):
            if not os.path.isdir(new_path):
                os.rename(old_path, new_path)
        else:
            os.makedirs(new_path, exist_ok=True)
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

    return new_path, drive_link


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

    policy_name = os.path.basename(policy_path.rstrip("/\\"))
    client_name = sanitize_name(client_name)
    deal_name = sanitize_name(f"Сделка - {deal_description}")
    dest_dir = os.path.join(GOOGLE_DRIVE_LOCAL_ROOT, client_name, deal_name)
    os.makedirs(dest_dir, exist_ok=True)
    new_path = os.path.join(dest_dir, policy_name)

    try:
        shutil.move(policy_path, new_path)
        logger.info("📁 Папка полиса перемещена: %s", new_path)
    except Exception:
        logger.exception("Не удалось переместить папку полиса")
        return None

    return new_path


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

    if not file_path or not os.path.isfile(file_path):
        return None

    os.makedirs(folder_path, exist_ok=True)
    dest = os.path.join(folder_path, os.path.basename(file_path))

    try:
        shutil.move(file_path, dest)
        logger.info("📄 Файл полиса перемещён: %s", dest)
    except Exception:
        logger.exception("Не удалось переместить файл полиса")
        return None

    return dest
