"""Утилиты для работы с локальными папками и Google Drive."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Optional, Tuple

from infrastructure.drive_gateway import DriveGateway, sanitize_drive_name

logger = logging.getLogger(__name__)


def sanitize_name(name: str) -> str:
    """Совместимый алиас для очистки имён путей."""

    return sanitize_drive_name(name)


def extract_folder_id(link: str | None) -> str | None:
    """Извлечь идентификатор папки из ссылки Google Drive."""

    if not link:
        return None

    return link.rstrip("/").split("/")[-1]


def is_drive_link(link: str | None) -> bool:
    """Проверить, что ссылка указывает на удалённое хранилище."""

    if not link:
        return False

    link = link.strip()
    if not link:
        return False

    if "://" in link:
        return True

    from urllib.parse import urlparse

    parsed = urlparse(link if "//" in link else f"//{link}", scheme="")
    host = (parsed.netloc or parsed.path).lower()
    if "google" in host:
        return True

    return False


def _resolve_base_path(
    gateway: DriveGateway, base_path: str | os.PathLike[str] | None
) -> Path:
    return Path(base_path) if base_path is not None else gateway.local_root


# ─────────────────────────── Работа с Google Drive ───────────────────────────


def create_drive_folder(
    folder_name: str,
    *,
    gateway: DriveGateway,
    parent_id: str | None = None,
) -> str:
    """Создать папку на Google Drive и вернуть ссылку."""

    return gateway.create_drive_folder(folder_name, parent_id)


def find_drive_folder(
    folder_name: str,
    *,
    gateway: DriveGateway,
    parent_id: str | None = None,
) -> str | None:
    """Найти папку на Google Drive и вернуть ссылку, если она существует."""

    return gateway.find_drive_folder(folder_name, parent_id)


def upload_to_drive(
    local_path: str | os.PathLike[str],
    drive_folder_id: str,
    *,
    gateway: DriveGateway,
) -> str:
    """Загрузить файл в указанную папку Google Drive и вернуть ссылку."""

    return gateway.upload_file(Path(local_path), drive_folder_id)


# ─────────────────────────── Локальные каталоги ─────────────────────────────


def create_client_drive_folder(
    client_name: str,
    *,
    gateway: DriveGateway,
    base_path: str | os.PathLike[str] | None = None,
) -> Tuple[str, Optional[str]]:
    """Создать локальную папку клиента и вернуть путь и ссылку.

    Returns:
        tuple[str, Optional[str]]: Кортеж из локального пути к созданной
        папке клиента и опциональной ссылки на удалённую директорию.
    """

    safe_name = sanitize_name(client_name)
    root = _resolve_base_path(gateway, base_path)
    local_path = root / safe_name

    if local_path.exists():
        logger.info("Папка клиента уже существует: %s", local_path)
    else:
        local_path.mkdir(parents=True, exist_ok=True)
        logger.info("Папка клиента создана: %s", local_path)

    return str(local_path), None


def create_deal_folder(
    client_name: str,
    deal_description: str,
    *,
    client_drive_link: str | None,
    gateway: DriveGateway,
    base_path: str | os.PathLike[str] | None = None,
) -> Tuple[str, Optional[str]]:
    """Создать локальную папку сделки и вернуть путь и ссылку.

    Returns:
        tuple[str, Optional[str]]: Кортеж из локального пути к папке
        сделки и опциональной ссылки на удалённую директорию клиента.
    """

    root = _resolve_base_path(gateway, base_path)
    deal_name = sanitize_name(f"Сделка - {deal_description}")
    local_path = root / sanitize_name(client_name) / deal_name

    if local_path.exists():
        logger.info("📂 Папка сделки уже существует: %s", local_path)
    else:
        local_path.mkdir(parents=True, exist_ok=True)
        logger.info("📁 Создана папка сделки: %s", local_path)

    return str(local_path), None


def create_policy_folder(
    client_name: str,
    policy_number: str,
    deal_description: str | None = None,
    *,
    gateway: DriveGateway,
    base_path: str | os.PathLike[str] | None = None,
) -> str:
    """Создать папку для полиса и вернуть её путь."""

    root = _resolve_base_path(gateway, base_path)
    client_root = root / sanitize_name(client_name)
    if deal_description:
        client_root /= sanitize_name(f"Сделка - {deal_description}")
    path = client_root / sanitize_name(f"Полис - {policy_number}")

    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def open_folder(path_or_url: str) -> None:
    """Открыть локальную папку или URL."""

    if not path_or_url:
        raise ValueError("Путь не задан.")

    path_or_url = path_or_url.strip()
    path = Path(path_or_url)

    if path.is_dir():
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
                                except Exception:  # noqa: BLE001
                                    pass
                                return
                        except Exception:  # noqa: BLE001
                            continue
                    shell.Open(str(path))
                except Exception:  # noqa: BLE001
                    os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform.startswith("darwin"):
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Не удалось открыть каталог %s", path)
            raise OSError(f"Не удалось открыть каталог: {exc}") from exc

    webbrowser.open(path_or_url)


def copy_path_to_clipboard(path_or_url: str) -> None:
    """Копировать путь или ссылку в буфер обмена."""

    if not path_or_url:
        raise ValueError("Путь не задан.")

    try:
        from PySide6.QtGui import QGuiApplication
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Буфер обмена недоступен") from exc

    app = QGuiApplication.instance()
    if app is None:
        raise RuntimeError("Нет GUI-приложения для буфера обмена")

    app.clipboard().setText(path_or_url.strip())


def copy_text_to_clipboard(text: str) -> None:
    """Копировать текст в буфер обмена."""

    if not text:
        raise ValueError("Пустой текст.")

    try:
        from PySide6.QtGui import QGuiApplication
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Буфер обмена недоступен") from exc

    app = QGuiApplication.instance()
    if app is None:
        raise RuntimeError("Нет GUI-приложения для буфера обмена")

    app.clipboard().setText(text)


def create_directory(path: str | os.PathLike[str]) -> Path:
    """Создать каталог и вернуть его путь."""

    directory = Path(path)
    if directory.exists():
        raise FileExistsError("Такая папка уже существует.")

    try:
        directory.mkdir(parents=True, exist_ok=False)
    except PermissionError as exc:
        raise PermissionError("Нет прав для создания папки.") from exc
    except OSError as exc:
        logger.exception("Не удалось создать папку %s", directory)
        raise OSError(f"Не удалось создать папку: {exc}") from exc

    return directory


def rename_path(source: str | os.PathLike[str], new_name: str) -> Path:
    """Переименовать файл или каталог и вернуть новый путь."""

    src_path = Path(source)
    if not src_path.exists():
        raise FileNotFoundError("Объект не найден.")

    name = new_name.strip()
    if not name:
        raise ValueError("Имя не может быть пустым.")

    dst_path = src_path.with_name(name)
    if dst_path.exists():
        raise FileExistsError("Объект с таким именем уже существует.")

    try:
        src_path.rename(dst_path)
    except PermissionError as exc:
        raise PermissionError("Нет прав для переименования.") from exc
    except OSError as exc:
        logger.exception("Не удалось переименовать %s в %s", src_path, dst_path)
        raise OSError(f"Не удалось переименовать объект: {exc}") from exc

    return dst_path


def delete_path(path: str | os.PathLike[str]) -> None:
    """Удалить файл или каталог."""

    target = Path(path)
    if not target.exists():
        raise FileNotFoundError("Объект уже удалён или недоступен.")

    try:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    except PermissionError as exc:
        raise PermissionError("Нет прав для удаления.") from exc
    except OSError as exc:
        logger.exception("Не удалось удалить %s", target)
        raise OSError(f"Не удалось удалить объект: {exc}") from exc


def rename_client_folder(
    old_name: str,
    new_name: str,
    drive_link: str | None,
    *,
    gateway: DriveGateway,
    base_path: str | os.PathLike[str] | None = None,
) -> Tuple[str, str | None]:
    """Переименовать папку клиента локально и на Google Drive."""

    root = _resolve_base_path(gateway, base_path)
    old_path = root / sanitize_name(old_name)
    new_path = root / sanitize_name(new_name)

    try:
        if old_path.is_dir():
            if not new_path.is_dir():
                old_path.rename(new_path)
        else:
            new_path.mkdir(parents=True, exist_ok=True)
    except Exception:  # noqa: BLE001
        logger.exception("Не удалось переименовать локальную папку клиента")

    if drive_link:
        file_id = extract_folder_id(drive_link)
        if file_id:
            try:
                gateway.rename_drive_folder(file_id, new_name)
            except Exception:  # noqa: BLE001
                logger.exception("Не удалось переименовать папку клиента на Drive")

    return str(new_path), drive_link


def rename_deal_folder(
    old_client_name: str,
    old_description: str,
    new_client_name: str,
    new_description: str,
    drive_link: str | None,
    current_path: str | os.PathLike[str] | None = None,
    *,
    gateway: DriveGateway,
    base_path: str | os.PathLike[str] | None = None,
) -> Tuple[str, str | None]:
    """Переименовать или переместить папку сделки и вернуть новый путь."""

    root = _resolve_base_path(gateway, base_path)
    default_old_path = (
        root
        / sanitize_name(old_client_name)
        / sanitize_name(f"Сделка - {old_description}")
    )
    old_path = (
        Path(current_path)
        if current_path and Path(current_path).is_dir()
        else default_old_path
    )
    new_path = (
        root
        / sanitize_name(new_client_name)
        / sanitize_name(f"Сделка - {new_description}")
    )

    try:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        if old_path.is_dir():
            if not new_path.is_dir():
                old_path.rename(new_path)
                logger.info("📂 Папка сделки перемещена: %s → %s", old_path, new_path)
        elif not new_path.is_dir():
            new_path.mkdir(parents=True, exist_ok=True)
            logger.info("📁 Создана новая папка сделки: %s", new_path)
    except Exception:  # noqa: BLE001
        logger.exception("Не удалось переименовать локальную папку сделки")

    if drive_link:
        file_id = extract_folder_id(drive_link)
        if file_id:
            try:
                gateway.rename_drive_folder(
                    file_id, sanitize_name(f"Сделка - {new_description}")
                )
            except Exception:  # noqa: BLE001
                logger.exception("Не удалось переименовать папку сделки на Drive")

    return str(new_path), drive_link


def rename_policy_folder(
    old_client_name: str,
    old_policy_number: str,
    old_deal_desc: str | None,
    new_client_name: str,
    new_policy_number: str,
    new_deal_desc: str | None,
    drive_link: str | None,
    *,
    gateway: DriveGateway,
    base_path: str | os.PathLike[str] | None = None,
) -> Tuple[str, str | None]:
    """Переименовать папку полиса."""

    root = _resolve_base_path(gateway, base_path)
    old_path = root / sanitize_name(old_client_name)
    if old_deal_desc:
        old_path /= sanitize_name(f"Сделка - {old_deal_desc}")
    old_path /= sanitize_name(f"Полис - {old_policy_number}")

    new_path = root / sanitize_name(new_client_name)
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
    except Exception:  # noqa: BLE001
        logger.exception("Не удалось переименовать локальную папку полиса")

    file_id = extract_folder_id(drive_link) if is_drive_link(drive_link) else None
    if file_id:
        try:
            gateway.rename_drive_folder(
                file_id, sanitize_name(f"Полис - {new_policy_number}")
            )
        except Exception:  # noqa: BLE001
            logger.exception("Не удалось переименовать папку полиса на Drive")

    return str(new_path), drive_link


def move_policy_folder_to_deal(
    policy_path: str | None,
    client_name: str,
    deal_description: str,
    *,
    gateway: DriveGateway,
    base_path: str | os.PathLike[str] | None = None,
) -> str | None:
    """Переместить папку полиса в папку сделки."""

    if not policy_path:
        return None

    root = _resolve_base_path(gateway, base_path)
    policy_name = Path(policy_path).name
    dest_dir = (
        root / sanitize_name(client_name) / sanitize_name(f"Сделка - {deal_description}")
    )
    dest_dir.mkdir(parents=True, exist_ok=True)
    new_path = dest_dir / policy_name

    try:
        shutil.move(policy_path, new_path)
        logger.info("📁 Папка полиса перемещена: %s", new_path)
    except Exception:  # noqa: BLE001
        logger.exception("Не удалось переместить папку полиса")
        return None

    return str(new_path)


def move_file_to_folder(
    file_path: str | os.PathLike[str],
    folder_path: str | os.PathLike[str],
) -> str | None:
    """Переместить файл в указанную папку."""

    src = Path(file_path)
    if not src.is_file():
        return None

    folder = Path(folder_path)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / src.name

    try:
        shutil.move(str(src), dest)
        logger.info("📄 Файл перемещён: %s", dest)
    except Exception:  # noqa: BLE001
        logger.exception("Не удалось переместить файл")
        return None

    return str(dest)
