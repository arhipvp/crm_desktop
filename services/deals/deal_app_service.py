"""Фасад для работы с данными сделок без раскрытия Peewee наружу."""

from __future__ import annotations

from collections.abc import Iterable as IterableABC
from typing import Mapping, MutableMapping, Sequence

from peewee import JOIN

from database.models import Client, Deal, DealExecutor, Executor
from services.deal_service import (
    build_deal_query,
    fetch_deals_page_with_total,
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
        fetch_page_with_total=fetch_deals_page_with_total,
        statuses_provider=get_distinct_statuses,
    ) -> None:
        self._build_query = build_query
        self._page_query = page_query
        self._fetch_page_with_total = fetch_page_with_total
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
        items, total = self._fetch_page_with_total(
            page,
            per_page,
            order_by=order_by or "reminder_date",
            order_dir=order_dir,
            column_filters=column_filters,
            **filters,
        )
        return deals_to_row_dtos(items), total

    def count(self, **filters) -> int:
        column_filters = self._convert_column_filters(filters.pop("column_filters", None))
        filters.pop("order_by", None)
        filters.pop("order_dir", None)
        query = self._build_query(column_filters=column_filters, **filters)
        return query.count()

    def get_statuses(self) -> Sequence[str]:
        return tuple(self._statuses_provider())

    def get_distinct_values(
        self,
        column_key: str,
        *,
        filters: Mapping[str, object] | None = None,
    ) -> list[dict[str, object]] | None:
        filters = dict(filters or {})
        search_text = str(filters.get("search_text") or "")
        show_deleted = bool(filters.get("show_deleted"))
        show_closed = bool(filters.get("show_closed"))

        raw_column_filters = dict(filters.get("column_filters") or {})
        raw_column_filters.pop(column_key, None)
        column_filters = self._convert_column_filters(raw_column_filters)

        query = self._build_query(
            search_text=search_text,
            show_deleted=show_deleted,
            show_closed=show_closed,
            column_filters=column_filters,
        )

        if column_key == "executor":
            executor_query = (
                Executor.select(Executor.full_name)
                .join(DealExecutor)
                .where(DealExecutor.deal.in_(query.select(Deal.id).distinct()))
                .where(Executor.full_name.is_null(False))
                .distinct()
                .order_by(Executor.full_name.asc())
            )
            values = [
                {"value": executor.full_name, "display": executor.full_name}
                for executor in executor_query
            ]
            null_executor_exists = (
                query.select(Deal.id)
                .switch(Deal)
                .join(DealExecutor, JOIN.LEFT_OUTER)
                .join(Executor, JOIN.LEFT_OUTER)
                .where(
                    (DealExecutor.id.is_null(True))
                    | (Executor.full_name.is_null(True))
                )
                .limit(1)
                .exists()
            )
            if null_executor_exists:
                values.insert(0, {"value": None, "display": "—"})
            return values

        if column_key == "status":
            rows = (
                Deal.select(Deal.status)
                .where(Deal.id.in_(query.select(Deal.id).distinct()))
                .where(Deal.status.is_null(False))
                .distinct()
                .order_by(Deal.status.asc())
            )
            values = [
                {"value": row.status, "display": row.status}
                for row in rows
            ]
            if (
                query.select(Deal.status)
                .where(Deal.status.is_null(True))
                .limit(1)
                .exists()
            ):
                values.insert(0, {"value": None, "display": "—"})
            return values

        if column_key == "client":
            rows = (
                Client.select(Client.name)
                .join(Deal)
                .where(Deal.id.in_(query.select(Deal.id).distinct()))
                .where(Client.name.is_null(False))
                .distinct()
                .order_by(Client.name.asc())
            )
            values = [
                {"value": row.name, "display": row.name}
                for row in rows
            ]
            if (
                query.select(Client.name)
                .where(Client.name.is_null(True))
                .limit(1)
                .exists()
            ):
                values.insert(0, {"value": None, "display": "—"})
            return values

        if column_key == "closed_reason":
            rows = (
                Deal.select(Deal.closed_reason)
                .where(Deal.id.in_(query.select(Deal.id).distinct()))
                .where(Deal.closed_reason.is_null(False))
                .distinct()
                .order_by(Deal.closed_reason.asc())
            )
            values = [
                {"value": row.closed_reason, "display": row.closed_reason}
                for row in rows
            ]
            if (
                query.select(Deal.closed_reason)
                .where(Deal.closed_reason.is_null(True))
                .limit(1)
                .exists()
            ):
                values.insert(0, {"value": None, "display": "—"})
            return values

        target_field = self._COLUMN_FILTER_MAP.get(column_key)
        if target_field is None:
            return None

        rows = (
            query.select(target_field)
            .where(target_field.is_null(False))
            .distinct()
            .order_by(target_field.asc())
        )

        values = [
            {"value": value, "display": value}
            for (value,) in rows.tuples()
        ]

        if (
            query.select(target_field)
            .where(target_field.is_null(True))
            .limit(1)
            .exists()
        ):
            values.insert(0, {"value": None, "display": "—"})

        return values

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
            normalized = self._normalize_filter_values(value)
            if not normalized:
                continue
            converted[field] = normalized
        return converted

    @staticmethod
    def _normalize_filter_values(value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            text = value.strip()
            return [text] if text else []
        if isinstance(value, IterableABC):
            result: list[str] = []
            for item in value:
                if item is None:
                    continue
                if isinstance(item, str):
                    text = item.strip()
                else:
                    text = str(item).strip()
                if text:
                    result.append(text)
            return result
        text = str(value).strip()
        return [text] if text else []


deal_app_service = DealAppService()
