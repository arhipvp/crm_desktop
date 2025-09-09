"""Работа с Google Sheets для синхронизации задач."""

from __future__ import annotations

import os
import logging
import re
from functools import lru_cache
from datetime import date

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
except Exception:  # noqa: BLE001
    Credentials = None  # type: ignore[assignment]
    build = lambda *a, **k: None  # type: ignore[assignment]

from database.models import Task
from services.task_crud import add_task, update_task
from services.validators import normalize_company_name

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_CREDENTIALS", "credentials.json")
GOOGLE_SHEETS_TASKS_ID = os.getenv("GOOGLE_SHEETS_TASKS_ID")
GOOGLE_SHEETS_CALCULATIONS_ID = os.getenv("GOOGLE_SHEETS_CALCULATIONS_ID")


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


def calculations_sheet_url() -> str | None:
    """Ссылка на таблицу расчётов из переменной окружения."""
    if not GOOGLE_SHEETS_CALCULATIONS_ID:
        return None
    return f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_CALCULATIONS_ID}"


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


def fetch_calculations() -> list[dict]:
    """Считать расчёты из таблицы и вернуть список словарей."""
    if not GOOGLE_SHEETS_CALCULATIONS_ID:
        return []
    rows = read_sheet(GOOGLE_SHEETS_CALCULATIONS_ID, "A1:Z")
    if not rows:
        return []
    headers = [h.strip().lower() for h in rows[0]]
    data: list[dict] = []
    for raw in rows[1:]:
        item = {h: (raw[i] if i < len(raw) else "") for i, h in enumerate(headers)}
        data.append(item)
    return data


def clear_rows(spreadsheet_id: str, start: int, end: int) -> None:
    """Очистить строки в указанном диапазоне (включительно)."""
    service = get_service()
    rng = f"A{start}:Z{end}"
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id, range=rng, body={}
    ).execute()


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


def _to_float(value: str | None) -> float | None:
    """Попытаться преобразовать строку в число."""
    if value is None:
        return None
    cleaned = re.sub(r"\s+", "", value)
    # извлечь первую группу цифр с возможной десятичной точкой
    match = re.search(r"[-+]?\d*[\.,]?\d+", cleaned)
    if not match:
        return None
    number = match.group(0).replace(",", ".")
    try:
        return float(number)
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


def sync_calculations_from_sheet() -> int:
    """Синхронизировать расчёты из Google Sheets с локальной БД."""
    logger.debug("Starting calculations sync")
    if not GOOGLE_SHEETS_CALCULATIONS_ID:
        logger.debug("GOOGLE_SHEETS_CALCULATIONS_ID is not set")
        return 0
    from services.calculation_service import add_calculation
    from database.models import DealCalculation

    rows = fetch_calculations()
    logger.debug("Fetched %s rows from sheet", len(rows))
    if not rows:
        return 0
    added = 0
    for item in rows:
        try:
            deal_id = int(item.get("deal_id", 0))
        except Exception:
            continue
        params = {
            "insurance_company": normalize_company_name(
                item.get("insurance_company", "")
            )
            if item.get("insurance_company")
            else None,
            "insurance_type": item.get("insurance_type"),
            "insured_amount": _to_float(item.get("insured_amount")),
            "premium": _to_float(item.get("premium")),
            "deductible": _to_float(item.get("deductible")),
            "note": item.get("note"),
        }

        # skip rows where all params are empty
        if all(v is None or v == "" for v in params.values()):
            continue

        exists = (
            DealCalculation.select()
            .where(
                (DealCalculation.deal_id == deal_id)
                & (DealCalculation.is_deleted == False)
                & (DealCalculation.insurance_company == params["insurance_company"])
                & (DealCalculation.insurance_type == params["insurance_type"])
                & (DealCalculation.insured_amount == params["insured_amount"])
                & (DealCalculation.premium == params["premium"])
                & (DealCalculation.deductible == params["deductible"])
                & (DealCalculation.note == params["note"])
            )
            .exists()
        )
        if exists:
            continue
        try:
            from database.db import db
            with db.atomic():
                add_calculation(deal_id, **params)
            added += 1
        except Exception:
            logger.exception("Failed to add calculation for %s", deal_id)
    logger.debug("Added %s calculations from sheet", added)
    return added
