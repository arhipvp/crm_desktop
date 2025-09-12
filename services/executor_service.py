import logging
from datetime import date
from typing import Iterable, List, Optional, Any

from peewee import JOIN, ModelSelect, Field

from services.query_utils import apply_search_and_filters

from config import Settings, get_settings
from database.db import db
from database.models import Deal, DealExecutor, Executor
from .task_states import QUEUED

logger = logging.getLogger(__name__)


def ensure_executors_from_env(settings: Settings | None = None) -> None:
    """Create Executor rows for APPROVED_EXECUTOR_IDS from settings."""
    settings = settings or get_settings()
    for eid in settings.approved_executor_ids:
        Executor.get_or_create(tg_id=eid, defaults={"full_name": str(eid)})


def get_executor(tg_id: int) -> Optional[Executor]:
    return Executor.get_or_none(Executor.tg_id == tg_id)


def ensure_executor(tg_id: int, full_name: str | None = None) -> Executor:
    ex, _ = Executor.get_or_create(
        tg_id=tg_id,
        defaults={"full_name": full_name or str(tg_id), "is_active": False},
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
    """Assign executor to a deal, replacing previous assignment."""
    executor = ensure_executor(tg_id)
    old_executor = get_executor_for_deal(deal_id)
    with db.atomic():
        DealExecutor.delete().where(DealExecutor.deal_id == deal_id).execute()
        DealExecutor.create(
            deal=deal_id, executor=executor, assigned_date=date.today(), note=note
        )
    logger.info("Executor %s assigned to deal %s", tg_id, deal_id)
    if old_executor and old_executor.tg_id != tg_id and is_approved(old_executor.tg_id):
        from services.telegram_service import notify_executor

        deal = Deal.get_or_none(Deal.id == deal_id)
        desc = f" — {deal.description}" if deal and deal.description else ""
        text = f"По сделке #{deal_id}{desc} исполнитель был сменен"
        notify_executor(old_executor.tg_id, text)


def unassign_executor(deal_id: int) -> None:
    """Remove executor assignment from a deal."""
    ex = get_executor_for_deal(deal_id)
    cnt = DealExecutor.delete().where(DealExecutor.deal_id == deal_id).execute()
    if cnt:
        logger.info("Executor unassigned from deal %s", deal_id)
        if ex and is_approved(ex.tg_id):
            from services.telegram_service import notify_executor

            deal = Deal.get_or_none(Deal.id == deal_id)
            desc = f" — {deal.description}" if deal and deal.description else ""
            text = f"По сделке #{deal_id}{desc} исполнитель был отвязан"
            notify_executor(ex.tg_id, text)


def get_executor_for_deal(deal_id: int) -> Optional[Executor]:
    de = DealExecutor.get_or_none(DealExecutor.deal_id == deal_id)
    return de.executor if de else None


def get_deals_for_executor(tg_id: int, *, only_with_tasks: bool = False) -> List[Deal]:
    query = (
        Deal.active()
        .join(DealExecutor, on=(Deal.id == DealExecutor.deal))
        .join(Executor)
        .where((Executor.tg_id == tg_id) & (Deal.is_closed == False))
    )

    if only_with_tasks:
        from database.models import Task
        task_subq = Task.active().where(Task.dispatch_state == QUEUED).select(Task.deal)
        query = query.where(Deal.id.in_(task_subq))

    return list(query)


def get_available_executors() -> Iterable[Executor]:
    ensure_executors_from_env()
    return Executor.select().where(Executor.is_active == True)


def build_executor_query(
    search_text: str = "",
    show_inactive: bool = True,
    column_filters: dict | None = None,
) -> ModelSelect:
    """Return filtered executors query."""
    query = Executor.select()
    if not show_inactive:
        query = query.where(Executor.is_active == True)
    query = apply_search_and_filters(query, Executor, search_text, column_filters)
    return query


def get_executors_page(
    page: int,
    per_page: int,
    search_text: str = "",
    show_inactive: bool = True,
    column_filters: dict | None = None,
    order_by: str | Field | Any = Executor.full_name,
    order_dir: str = "asc",
    **_: dict,
) -> ModelSelect:
    query = build_executor_query(search_text, show_inactive, column_filters)
    if isinstance(order_by, str):
        field = getattr(Executor, order_by, Executor.full_name)
    else:
        field = order_by
    order_func = field.desc if order_dir == "desc" else field.asc
    offset = (page - 1) * per_page
    return query.order_by(order_func()).limit(per_page).offset(offset)


def add_executor(**kwargs) -> Executor:
    allowed = {"full_name", "tg_id", "is_active"}
    data = {k: kwargs[k] for k in allowed if k in kwargs}
    data.setdefault("is_active", True)
    return Executor.create(**data)


def update_executor(executor: Executor, **kwargs) -> Executor:
    allowed = {"full_name", "tg_id", "is_active"}
    # Ignore None values to avoid overwriting NOT NULL fields with NULL
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return executor
    for k, v in updates.items():
        setattr(executor, k, v)
    executor.save()
    return executor
