import logging
from dataclasses import dataclass
from typing import Optional, Dict

logger = logging.getLogger(__name__)

@dataclass
class Executor:
    tg_id: int
    full_name: str | None = None
    is_approved: bool = False
    current_deal_id: int | None = None


# хранится только в памяти
_executors: Dict[int, Executor] = {}


def get_executor(tg_id: int) -> Optional[Executor]:
    """Получить исполнителя по Telegram ID."""
    return _executors.get(tg_id)


def ensure_executor(tg_id: int, full_name: str | None = None) -> Executor:
    """Вернуть исполнителя, создав запись при необходимости."""
    ex = _executors.get(tg_id)
    if not ex:
        ex = Executor(tg_id=tg_id, full_name=full_name)
        _executors[tg_id] = ex
    elif full_name and ex.full_name != full_name:
        ex.full_name = full_name
    return ex


def is_approved(tg_id: int) -> bool:
    ex = get_executor(tg_id)
    return bool(ex and ex.is_approved)


def approve_executor(tg_id: int):
    ex = ensure_executor(tg_id)
    if not ex.is_approved:
        ex.is_approved = True
        logger.info("Executor %s approved", tg_id)


def assign_deal(tg_id: int, deal_id: int) -> None:
    """Закрепить за исполнителем сделку."""
    ex = ensure_executor(tg_id)
    ex.current_deal_id = deal_id
    logger.info("Executor %s assigned deal %s", tg_id, deal_id)


def clear_deal(tg_id: int) -> None:
    """Отвязать исполнителя от текущей сделки."""
    ex = get_executor(tg_id)
    if ex and ex.current_deal_id is not None:
        ex.current_deal_id = None
        logger.info("Executor %s cleared from deal", tg_id)


def get_assigned_deal(tg_id: int) -> int | None:
    """Получить id сделки, закреплённой за исполнителем."""
    ex = get_executor(tg_id)
    return ex.current_deal_id if ex else None
