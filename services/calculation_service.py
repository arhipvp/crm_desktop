from datetime import datetime
import logging
from peewee import ModelSelect

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
    return DealCalculation.create(**data)


def get_calculations(deal_id: int) -> ModelSelect:
    return DealCalculation.select().where(
        (DealCalculation.deal_id == deal_id) & (DealCalculation.is_deleted == False)
    ).order_by(DealCalculation.created_at.desc())


def delete_calculation(entry_id: int) -> None:
    entry = DealCalculation.get_or_none(DealCalculation.id == entry_id)
    if entry:
        entry.is_deleted = True
        entry.save()
    else:
        logger.warning("Calculation entry %s not found", entry_id)

