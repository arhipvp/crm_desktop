import logging
import os
import re
from datetime import date
from typing import Optional, Iterable, List

from database.models import Executor, DealExecutor, Deal
from database.db import db

logger = logging.getLogger(__name__)


def _ids_from_env() -> list[int]:
    ids: list[int] = []
    for part in re.split(r"[ ,]+", os.getenv("APPROVED_EXECUTOR_IDS", "").strip()):
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            logger.warning("Invalid executor id: %s", part)
    return ids


def ensure_executors_from_env() -> None:
    """Создать записи исполнителей из переменной окружения, если их нет."""
    for eid in _ids_from_env():
        Executor.get_or_create(tg_id=eid, defaults={"full_name": str(eid)})


def get_executor(tg_id: int) -> Optional[Executor]:
    return Executor.get_or_none(Executor.tg_id == tg_id)


def ensure_executor(tg_id: int, full_name: str | None = None) -> Executor:
    ex, _ = Executor.get_or_create(
        tg_id=tg_id, defaults={"full_name": full_name or str(tg_id)}
    )
    if full_name and ex.full_name != full_name:
        ex.full_name = full_name
        ex.save(only=[Executor.full_name])
    return ex


def is_approved(tg_id: int) -> bool:
    ex = get_executor(tg_id)
    return bool(ex and ex.is_active)


def approve_executor(tg_id: int) -> None:
    ex = ensure_executor(tg_id)
    if not ex.is_active:
        ex.is_active = True
        ex.save(only=[Executor.is_active])
        logger.info("Executor %s approved", tg_id)


def assign_executor(deal_id: int, tg_id: int, note: str | None = None) -> None:
    """Привязать исполнителя к сделке."""
    executor = ensure_executor(tg_id)
    with db.atomic():
        DealExecutor.delete().where(DealExecutor.deal_id == deal_id).execute()
        DealExecutor.create(deal=deal_id, executor=executor, assigned_date=date.today(), note=note)
    logger.info("Executor %s assigned to deal %s", tg_id, deal_id)


def unassign_executor(deal_id: int) -> None:
    """Отвязать исполнителя от сделки."""
    cnt = DealExecutor.delete().where(DealExecutor.deal_id == deal_id).execute()
    if cnt:
        logger.info("Executor unassigned from deal %s", deal_id)


def get_executor_for_deal(deal_id: int) -> Optional[Executor]:
    de = DealExecutor.get_or_none(DealExecutor.deal_id == deal_id)
    return de.executor if de else None


def get_deals_for_executor(tg_id: int) -> List[Deal]:
    query = (
        Deal.select()
        .join(DealExecutor, on=(Deal.id == DealExecutor.deal))
        .join(Executor)
        .where((Executor.tg_id == tg_id) & (Deal.is_deleted == False))
    )
    return list(query)


def get_available_executors() -> Iterable[Executor]:
    ensure_executors_from_env()
    return Executor.select().where(Executor.is_active == True)
