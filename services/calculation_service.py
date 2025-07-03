from datetime import datetime
import logging
from typing import Iterable
from peewee import ModelSelect
import os
import pandas as pd

from database.models import Deal, DealCalculation

logger = logging.getLogger(__name__)


def add_calculation(deal_id: int, **kwargs) -> DealCalculation:
    deal = Deal.get_or_none((Deal.id == deal_id) & (Deal.is_deleted == False))
    if not deal:
        raise ValueError("Deal not found")

    allowed = {
        "insurance_company",
        "insurance_type",
        "insured_amount",
        "premium",
        "deductible",
        "note",
    }
    data = {k: v for k, v in kwargs.items() if k in allowed}
    data.setdefault("created_at", datetime.utcnow())
    data["deal"] = deal
    data["is_deleted"] = False
    entry = DealCalculation.create(**data)
    try:
        export_calculations_excel(deal_id)
    except Exception:
        logger.debug("Failed to export calculations", exc_info=True)
    try:
        from services.telegram_service import notify_admin
        msg = f"➕ Расчёт по сделке #{deal_id}: {format_calculation(entry)}"
        notify_admin(msg)
    except Exception:
        logger.debug("Failed to notify admin", exc_info=True)
    return entry


def get_calculations(deal_id: int, show_deleted: bool = False) -> ModelSelect:
    query = DealCalculation.select().where(DealCalculation.deal_id == deal_id)
    if not show_deleted:
        query = query.where(DealCalculation.is_deleted == False)
    return query.order_by(DealCalculation.created_at.desc())


def mark_calculation_deleted(entry_id: int) -> None:
    """Помечает расчёт удалённым."""
    entry = DealCalculation.get_or_none(DealCalculation.id == entry_id)
    if entry:
        entry.is_deleted = True
        entry.save()
    else:
        logger.warning("Calculation entry %s not found", entry_id)


# совместимый алиас на случай устаревших вызовов
delete_calculation = mark_calculation_deleted

# alias for BaseTableView automatic deletion
mark_dealcalculation_deleted = mark_calculation_deleted


def update_calculation(entry: DealCalculation, **kwargs) -> DealCalculation:
    """Update an existing calculation entry."""
    allowed = {
        "insurance_company",
        "insurance_type",
        "insured_amount",
        "premium",
        "deductible",
        "note",
        "deal_id",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if "deal_id" in updates:
        deal = Deal.get_or_none((Deal.id == updates["deal_id"]) & (Deal.is_deleted == False))
        if not deal:
            raise ValueError("Deal not found")
        entry.deal = deal
        updates.pop("deal_id")

    for key, value in updates.items():
        setattr(entry, key, value)

    if updates:
        entry.save()
        try:
            export_calculations_excel(entry.deal_id)
        except Exception:
            logger.debug("Failed to export calculations", exc_info=True)
    return entry


def get_unique_calculation_field_values(field_name: str) -> list[str]:
    """Return unique non-null values of a DealCalculation field."""
    allowed_fields = {"insurance_company", "insurance_type"}
    if field_name not in allowed_fields:
        raise ValueError(f"Invalid field: {field_name}")
    q = (
        DealCalculation.select(getattr(DealCalculation, field_name))
        .where(getattr(DealCalculation, field_name).is_null(False))
        .distinct()
    )
    return sorted(
        {getattr(c, field_name) for c in q if getattr(c, field_name)}
    )


def _fmt_num(v: float) -> str:
    """Форматирует число с пробелами между тысячами."""
    return f"{v:,.0f}".replace(",", " ")


def format_calculation(calc: DealCalculation) -> str:
    """Вернуть строку с параметрами расчёта."""
    header_parts = [p for p in (calc.insurance_company, calc.insurance_type) if p]
    header = ", ".join(header_parts) if header_parts else "-"
    details: list[str] = []
    if calc.insured_amount is not None:
        details.append(f"сумма {_fmt_num(calc.insured_amount)} руб")
    if calc.premium is not None:
        details.append(f"премия {_fmt_num(calc.premium)} руб")
    if calc.deductible is not None:
        details.append(f"франшиза {_fmt_num(calc.deductible)} руб")
    line = header
    if details:
        line += ": " + ", ".join(details)
    if calc.note:
        line += f" — {calc.note}"
    return line


def generate_offer_text(calculations: Iterable[DealCalculation]) -> str:
    """Формирует текстовое предложение для клиента по выбранным расчётам."""
    lines: list[str] = []
    sorted_calcs = sorted(
        list(calculations), key=lambda c: (c.insurance_type or "", c.insurance_company or "")
    )
    for calc in sorted_calcs:
        header = ", ".join(
            [
                str(c)
                for c in [calc.insurance_company, calc.insurance_type]
                if c
            ]
        )
        details = []
        if calc.insured_amount is not None:
            details.append(f"сумма {_fmt_num(calc.insured_amount)} руб")
        if calc.premium is not None:
            details.append(f"премия {_fmt_num(calc.premium)} руб")
        if calc.deductible is not None:
            details.append(f"франшиза {_fmt_num(calc.deductible)} руб")
        line = header
        if details:
            line += ": " + ", ".join(details)
        lines.append(line)
    return "\n".join(lines)


def export_calculations_excel(deal_id: int) -> str:
    """Экспортировать расчёты сделки в Excel и вернуть путь к файлу."""
    deal = Deal.get_or_none(Deal.id == deal_id)
    if not deal:
        raise ValueError("Deal not found")

    folder = deal.drive_folder_path
    if not folder:
        raise ValueError("Deal folder not set")

    calcs = list(get_calculations(deal_id))
    data = [
        {
            "Страховая компания": c.insurance_company,
            "Вид страхования": c.insurance_type,
            "Страховая сумма": c.insured_amount,
            "Премия": c.premium,
            "Франшиза": c.deductible,
            "Комментарий": c.note,
            "Создано": c.created_at,
        }
        for c in calcs
    ]
    df = pd.DataFrame(data)
    file_name = f"calculations_{deal_id}.xlsx"
    path = os.path.join(folder, file_name)
    df.to_excel(path, index=False)
    return path

