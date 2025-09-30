from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config import Settings

try:  # pragma: no cover - опциональные зависимости
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except Exception:  # noqa: BLE001
    Credentials = None  # type: ignore[assignment]
    build = None  # type: ignore[assignment]
    MediaFileUpload = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]


def sanitize_drive_name(name: str) -> str:
    """Очистить имя от недопустимых символов для файлов/папок."""

    cleaned = re.sub(r'[<>:"/\\|?*\n\r\t]', "_", name)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned.rstrip(" .")


@dataclass
class DriveGateway:
    """Адаптер для работы с локальными каталогами и Google Drive."""

    settings: Settings
    _service: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._local_root = Path(self.settings.google_drive_local_root).expanduser()

    @property
    def local_root(self) -> Path:
        """Базовый каталог синхронизации Google Drive."""

        return self._local_root

    def build_local_path(
        self, *parts: str, base_path: Path | None = None
    ) -> Path:
        """Сформировать путь внутри локального корня, очищая части пути."""

        base = Path(base_path) if base_path is not None else self.local_root
        sanitized_parts = [sanitize_drive_name(part) for part in parts if part]
        return base.joinpath(*sanitized_parts)

    def ensure_local_directory(
        self, *parts: str, base_path: Path | None = None
    ) -> Path:
        """Убедиться, что директория существует, и вернуть её путь."""

        path = self.build_local_path(*parts, base_path=base_path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    # ─────────────────────────── Google Drive ──────────────────────────

    def _get_service(self):
        if self._service is not None:
            return self._service
        if Credentials is None or build is None:
            raise RuntimeError("Google Drive libraries are not available")
        credentials_path = Path(
            self.settings.drive_service_account_file
        ).expanduser()
        creds = Credentials.from_service_account_file(
            str(credentials_path), scopes=SCOPES
        )
        self._service = build("drive", "v3", credentials=creds)
        return self._service

    def create_drive_folder(
        self, folder_name: str, parent_id: str | None = None
    ) -> str:
        """Создать папку на Google Drive и вернуть ссылку на неё."""

        parent = parent_id or self.settings.drive_root_folder_id
        if not parent:
            raise ValueError("Drive root folder id is not configured")

        service = self._get_service()
        safe_name = sanitize_drive_name(folder_name)
        query = (
            f"'{parent}' in parents and name = '{safe_name}' and "
            "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )
        response = (
            service.files()
            .list(q=query, fields="files(id)", spaces="drive")
            .execute()
        )
        files = response.get("files", [])
        if files:
            folder_id = files[0]["id"]
            return f"https://drive.google.com/drive/folders/{folder_id}"

        metadata = {
            "name": safe_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent],
        }
        folder = service.files().create(body=metadata, fields="id").execute()
        return f"https://drive.google.com/drive/folders/{folder['id']}"

    def find_drive_folder(
        self, folder_name: str, parent_id: str | None = None
    ) -> str | None:
        """Найти существующую папку на Google Drive и вернуть ссылку."""

        parent = parent_id or self.settings.drive_root_folder_id
        if not parent:
            return None

        service = self._get_service()
        safe_name = sanitize_drive_name(folder_name)
        query = (
            f"'{parent}' in parents and name = '{safe_name}' and "
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

    def upload_file(self, local_path: Path, drive_folder_id: str) -> str:
        """Загрузить файл в указанную папку Google Drive."""

        if MediaFileUpload is None:
            raise RuntimeError("Google Drive libraries are not available")

        service = self._get_service()
        file_metadata = {
            "name": local_path.name,
            "parents": [drive_folder_id],
        }
        media = MediaFileUpload(str(local_path), resumable=True)
        uploaded = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id, webViewLink")
            .execute()
        )
        logger.info("☁️ Загружен: %s", uploaded["webViewLink"])
        return uploaded["webViewLink"]

    def rename_drive_folder(self, file_id: str, new_name: str) -> None:
        """Переименовать папку на Google Drive."""

        service = self._get_service()
        service.files().update(
            fileId=file_id,
            body={"name": sanitize_drive_name(new_name)},
            fields="id",
        ).execute()
