import logging
from dataclasses import dataclass
from typing import Optional, Dict

logger = logging.getLogger(__name__)

@dataclass
class Executor:
    tg_id: int
    full_name: str | None = None
    is_approved: bool = False


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
