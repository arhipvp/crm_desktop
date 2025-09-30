"""Сервисы синхронизации данных с Google Sheets."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from config import Settings
from database.db import db
from database.models import DealCalculation, Task
from infrastructure.sheets_gateway import SheetsGateway
from services.calculation_service import add_calculation
from services.task_crud import add_task, update_task
from services.validators import normalize_company_name

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskRow:
    """Строка задачи из таблицы."""

    title: str
    due_date: date
    note: str | None = None


@dataclass(frozen=True)
class CalculationRow:
    """Строка расчёта сделки из таблицы."""

    deal_id: int
    insurance_company: str | None
    insurance_type: str | None
    insured_amount: float | None
    premium: float | None
    deductible: float | None
    note: str | None


class TaskRepository:
    """Работа с задачами в базе данных."""

    def find_by_title_and_due_date(self, title: str, due: date) -> Task | None:
        return Task.get_or_none((Task.title == title) & (Task.due_date == due))

    def create_task(self, row: TaskRow) -> Task:
        with db.atomic():
            return add_task(title=row.title, due_date=row.due_date, note=row.note)

    def update_task_note(self, task: Task, note: str | None) -> Task:
        with db.atomic():
            return update_task(task, note=note)


class DealCalculationRepository:
    """Работа с расчётами сделок."""

    def exists(self, row: CalculationRow) -> bool:
        return (
            DealCalculation.select()
            .where(
                (DealCalculation.deal_id == row.deal_id)
                & (DealCalculation.is_deleted == False)
                & (DealCalculation.insurance_company == row.insurance_company)
                & (DealCalculation.insurance_type == row.insurance_type)
                & (DealCalculation.insured_amount == row.insured_amount)
                & (DealCalculation.premium == row.premium)
                & (DealCalculation.deductible == row.deductible)
                & (DealCalculation.note == row.note)
            )
            .exists()
        )

    def add(self, row: CalculationRow) -> None:
        with db.atomic():
            add_calculation(
                row.deal_id,
                insurance_company=row.insurance_company,
                insurance_type=row.insurance_type,
                insured_amount=row.insured_amount,
                premium=row.premium,
                deductible=row.deductible,
                note=row.note,
            )


class SheetsSyncService:
    """Оркестратор синхронизации Google Sheets с локальной базой."""

    def __init__(
        self,
        settings: Settings,
        gateway: SheetsGateway,
        task_repository: TaskRepository,
        calculation_repository: DealCalculationRepository,
    ) -> None:
        self._settings = settings
        self._gateway = gateway
        self._task_repository = task_repository
        self._calculation_repository = calculation_repository

    # ─────────────────────────── публичные методы ───────────────────────────

    def tasks_sheet_url(self) -> str | None:
        sheet_id = self._settings.google_sheets_tasks_id
        if not sheet_id:
            return None
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}"

    def calculations_sheet_url(self) -> str | None:
        sheet_id = self._settings.google_sheets_calculations_id
        if not sheet_id:
            return None
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}"

    def fetch_tasks(self) -> list[dict[str, str]]:
        sheet_id = self._settings.google_sheets_tasks_id
        if not sheet_id:
            return []
        rows = self._gateway.read_sheet(sheet_id, "A1:Z")
        return self._rows_to_dicts(rows)

    def fetch_calculations(self) -> list[dict[str, str]]:
        sheet_id = self._settings.google_sheets_calculations_id
        if not sheet_id:
            return []
        rows = self._gateway.read_sheet(sheet_id, "A1:Z")
        return self._rows_to_dicts(rows)

    def sync_tasks(self) -> int:
        added = 0
        for row in self._iter_task_rows(self.fetch_tasks()):
            existing = self._task_repository.find_by_title_and_due_date(
                row.title, row.due_date
            )
            if existing:
                self._task_repository.update_task_note(existing, row.note)
                continue
            self._task_repository.create_task(row)
            added += 1
        return added

    def sync_calculations(self) -> int:
        logger.debug("Начинаем синхронизацию расчётов из Google Sheets")
        added = 0
        for row in self._iter_calculation_rows(self.fetch_calculations()):
            if self._calculation_repository.exists(row):
                continue
            try:
                self._calculation_repository.add(row)
                added += 1
            except Exception:  # noqa: BLE001
                logger.exception("Не удалось добавить расчёт для сделки %s", row.deal_id)
        logger.debug("Добавлено %s расчётов из листа", added)
        return added

    # ─────────────────────────── внутренние методы ──────────────────────────

    @staticmethod
    def _rows_to_dicts(rows: list[list[str]]) -> list[dict[str, str]]:
        if not rows:
            return []
        headers = [h.strip().lower() for h in rows[0]]
        result: list[dict[str, str]] = []
        for raw in rows[1:]:
            item: dict[str, str] = {}
            for index, header in enumerate(headers):
                item[header] = raw[index] if index < len(raw) else ""
            result.append(item)
        return result

    def _iter_task_rows(self, rows: Iterable[dict[str, str]]) -> Iterable[TaskRow]:
        for item in rows:
            title = item.get("title") or item.get("задача") or item.get("task")
            if not title:
                continue
            due = self._parse_date(item.get("due_date", "")) or date.today()
            note = item.get("note") or None
            yield TaskRow(title=title, due_date=due, note=note)

    def _iter_calculation_rows(
        self, rows: Iterable[dict[str, str]]
    ) -> Iterable[CalculationRow]:
        for item in rows:
            try:
                deal_id = int(item.get("deal_id", 0))
            except Exception:
                continue

            insurance_company_raw = item.get("insurance_company")
            insurance_company = (
                normalize_company_name(insurance_company_raw)
                if insurance_company_raw
                else None
            )
            row = CalculationRow(
                deal_id=deal_id,
                insurance_company=insurance_company,
                insurance_type=item.get("insurance_type") or None,
                insured_amount=self._to_float(item.get("insured_amount")),
                premium=self._to_float(item.get("premium")),
                deductible=self._to_float(item.get("deductible")),
                note=item.get("note") or None,
            )

            if all(value in {None, ""} for value in (
                row.insurance_company,
                row.insurance_type,
                row.insured_amount,
                row.premium,
                row.deductible,
                row.note,
            )):
                continue

            yield row

    @staticmethod
    def _parse_date(value: str | None) -> date | None:
        if not value:
            return None
        text = value.strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except Exception:  # noqa: BLE001
            try:
                day, month, year = text.split(".")
                return date(int(year), int(month), int(day))
            except Exception:  # noqa: BLE001
                return None

    @staticmethod
    def _to_float(value: str | None) -> float | None:
        if value is None:
            return None
        cleaned = re.sub(r"\s+", "", value)
        match = re.search(r"[-+]?\d*[\.,]?\d+", cleaned)
        if not match:
            return None
        number = match.group(0).replace(",", ".")
        try:
            return float(number)
        except Exception:  # noqa: BLE001
            return None


__all__ = [
    "SheetsSyncService",
    "TaskRepository",
    "DealCalculationRepository",
    "TaskRow",
    "CalculationRow",
]

