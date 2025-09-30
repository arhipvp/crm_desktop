"""Фасад для работы с данными сделок без раскрытия Peewee наружу."""

from __future__ import annotations

from typing import Mapping, MutableMapping, Sequence

from database.models import Client, Deal, Executor
from services.deal_service import (
    build_deal_query,
    get_deals_page,
    get_distinct_statuses,
)

from .dto import DealRowDTO, deals_to_row_dtos

__all__ = ["DealAppService", "deal_app_service"]


class DealAppService:
    """Фасад, возвращающий DTO вместо моделей Peewee."""

    _COLUMN_FILTER_MAP: Mapping[str, object] = {
        "reminder_date": Deal.reminder_date,
        "client": Client.name,
        "status": Deal.status,
        "description": Deal.description,
        "calculations": Deal.calculations,
        "start_date": Deal.start_date,
        "is_closed": Deal.is_closed,
        "closed_reason": Deal.closed_reason,
        "executor": Executor.full_name,
    }

    def __init__(
        self,
        *,
        build_query=build_deal_query,
        page_query=get_deals_page,
        statuses_provider=get_distinct_statuses,
    ) -> None:
        self._build_query = build_query
        self._page_query = page_query
        self._statuses_provider = statuses_provider

    # ------------------------------------------------------------------
    # Чтение данных
    # ------------------------------------------------------------------
    def get_page(
        self,
        page: int,
        per_page: int,
        *,
        order_by: str | None = None,
        order_dir: str = "asc",
        **filters,
    ) -> tuple[list[DealRowDTO], int]:
        column_filters = self._convert_column_filters(filters.pop("column_filters", None))
        items = self._page_query(
            page,
            per_page,
            order_by=order_by or "reminder_date",
            order_dir=order_dir,
            column_filters=column_filters,
            **filters,
        )
        query = self._build_query(
            column_filters=column_filters,
            **filters,
        )
        total = query.count()
        return deals_to_row_dtos(items), total

    def count(self, **filters) -> int:
        column_filters = self._convert_column_filters(filters.pop("column_filters", None))
        query = self._build_query(column_filters=column_filters, **filters)
        return query.count()

    def get_statuses(self) -> Sequence[str]:
        return tuple(self._statuses_provider())

    # ------------------------------------------------------------------
    # Вспомогательные методы
    # ------------------------------------------------------------------
    def _convert_column_filters(
        self, column_filters: MutableMapping[object, object] | None
    ) -> dict:
        if not column_filters:
            return {}
        converted: dict = {}
        for key, value in column_filters.items():
            name = getattr(key, "name", key)
            field = self._COLUMN_FILTER_MAP.get(str(name))
            if field is None:
                continue
            converted[field] = value
        return converted


deal_app_service = DealAppService()
