"""Адаптер для работы с Google Sheets."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config import Settings

try:  # pragma: no cover - опциональные зависимости
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
except Exception:  # noqa: BLE001
    Credentials = None  # type: ignore[assignment]
    build = None  # type: ignore[assignment]

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@dataclass
class SheetsGateway:
    """Ленивая обёртка над Google Sheets API."""

    settings: Settings
    _service: Any = field(default=None, init=False, repr=False)

    def _get_service(self):
        if self._service is not None:
            return self._service
        if Credentials is None or build is None:
            raise RuntimeError("Google Sheets libraries are not available")

        credentials_path = Path(
            self.settings.sheets_service_account_file
        ).expanduser()
        creds = Credentials.from_service_account_file(
            str(credentials_path), scopes=SCOPES
        )
        self._service = build("sheets", "v4", credentials=creds)
        return self._service

    def read_sheet(self, spreadsheet_id: str, range_name: str) -> list[list[str]]:
        """Прочитать диапазон из таблицы."""

        service = self._get_service()
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=range_name)
            .execute()
        )
        values = result.get("values", [])
        # Копия списка для предотвращения неожиданных мутаций вызывающим кодом
        return [list(row) for row in values]

    def append_rows(
        self, spreadsheet_id: str, range_name: str, rows: list[list[str]]
    ) -> None:
        """Добавить строки в таблицу."""

        service = self._get_service()
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body={"values": rows},
        ).execute()

    def clear_rows(self, spreadsheet_id: str, start: int, end: int) -> None:
        """Очистить указанный диапазон строк."""

        service = self._get_service()
        rng = f"A{start}:Z{end}"
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id, range=rng, body={}
        ).execute()


__all__ = ["SheetsGateway"]

