import logging
from typing import Optional

from database.models import Executor

logger = logging.getLogger(__name__)


def get_executor(tg_id: int) -> Optional[Executor]:
    """Получить исполнителя по Telegram ID."""
    return Executor.get_or_none(Executor.tg_id == tg_id)


def ensure_executor(tg_id: int, full_name: str | None = None) -> Executor:
    """Вернуть исполнителя, создав запись при необходимости."""
    ex, _ = Executor.get_or_create(tg_id=tg_id, defaults={"full_name": full_name})
    if full_name and ex.full_name != full_name:
        ex.full_name = full_name
        ex.save()
    return ex


def is_approved(tg_id: int) -> bool:
    ex = get_executor(tg_id)
    return bool(ex and ex.is_approved)


def approve_executor(tg_id: int):
    ex = ensure_executor(tg_id)
    if not ex.is_approved:
        ex.is_approved = True
        ex.save()
        logger.info("Executor %s approved", tg_id)

