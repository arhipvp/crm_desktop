"""Работа с Google Sheets для синхронизации задач."""

from __future__ import annotations

import os
import logging
from functools import lru_cache
from datetime import date

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
except Exception:  # noqa: BLE001
    Credentials = None  # type: ignore[assignment]
    build = lambda *a, **k: None  # type: ignore[assignment]

from database.models import Task
from services.task_service import add_task, update_task

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_CREDENTIALS", "credentials.json")
GOOGLE_SHEETS_TASKS_ID = os.getenv("GOOGLE_SHEETS_TASKS_ID")


@lru_cache(maxsize=1)
def get_service():
    """Создать и кешировать клиент Google Sheets."""
    if Credentials is None:
        raise RuntimeError("Google Sheets libraries are not available")
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def read_sheet(spreadsheet_id: str, range_name: str) -> list[list[str]]:
    """Получить диапазон значений из таблицы."""
    service = get_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_name)
        .execute()
    )
    return result.get("values", [])


def append_rows(spreadsheet_id: str, range_name: str, rows: list[list[str]]) -> None:
    """Добавить строки в таблицу."""
    service = get_service()
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()


def tasks_sheet_url() -> str | None:
    """Ссылка на таблицу задач из переменной окружения."""
    if not GOOGLE_SHEETS_TASKS_ID:
        return None
    return f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_TASKS_ID}"


def fetch_tasks() -> list[dict]:
    """Считать задачи из таблицы и вернуть список словарей."""
    if not GOOGLE_SHEETS_TASKS_ID:
        return []
    rows = read_sheet(GOOGLE_SHEETS_TASKS_ID, "A1:Z")
    if not rows:
        return []
    headers = [h.strip().lower() for h in rows[0]]
    data: list[dict] = []
    for raw in rows[1:]:
        item = {h: (raw[i] if i < len(raw) else "") for i, h in enumerate(headers)}
        data.append(item)
    return data


def _parse_date(value: str) -> date | None:
    value = value.strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except Exception:
        try:
            # формат dd.mm.yyyy
            d, m, y = value.split(".")
            return date(int(y), int(m), int(d))
        except Exception:
            return None


def sync_tasks_from_sheet() -> int:
    """Синхронизировать задачи из Google Sheets с локальной БД."""
    tasks = fetch_tasks()
    added = 0
    for item in tasks:
        title = item.get("title") or item.get("задача") or item.get("task")
        due = _parse_date(item.get("due_date", "")) or date.today()
        note = item.get("note")
        if not title:
            continue
        existing = Task.get_or_none((Task.title == title) & (Task.due_date == due))
        if existing:
            update_task(existing, note=note)
        else:
            add_task(title=title, due_date=due, note=note)
            added += 1
    return added
