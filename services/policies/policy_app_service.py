"""Прикладной сервис для работы с таблицей полисов."""

from __future__ import annotations

from typing import Any, Sequence

from peewee import Field

from database.db import db
from database.models import Client, Deal, Policy
from services.policies.policy_service import (
    attach_premium,
    build_policy_query,
    mark_policies_deleted,
)
from infrastructure.drive_gateway import DriveGateway

from .dto import PolicyRowDTO


class PolicyAppService:
    """Фасад между UI и доменным уровнем сервисов полисов."""

    _FIELD_ALIASES: dict[str, Field] = {
        "client_name": Client.name,
        "deal_description": Deal.description,
        "policy_number": Policy.policy_number,
        "insurance_type": Policy.insurance_type,
        "insurance_company": Policy.insurance_company,
        "contractor": Policy.contractor,
        "sales_channel": Policy.sales_channel,
        "start_date": Policy.start_date,
        "end_date": Policy.end_date,
        "vehicle_brand": Policy.vehicle_brand,
        "vehicle_model": Policy.vehicle_model,
        "vehicle_vin": Policy.vehicle_vin,
        "note": Policy.note,
        "drive_folder_link": Policy.drive_folder_link,
        "renewed_to": Policy.renewed_to,
    }

    def get_page(
        self,
        page: int,
        per_page: int,
        *,
        order_by: Any | None = None,
        order_dir: str = "asc",
        **filters: Any,
    ) -> list[PolicyRowDTO]:
        column_filters = filters.pop("column_filters", None)
        prepared_filters = self._prepare_column_filters(column_filters)
        order_field = self._resolve_order_field(order_by)
        query = build_policy_query(
            column_filters=prepared_filters,
            order_by=order_field,
            **filters,
        )
        if order_field is not None:
            ordering = order_field.desc() if order_dir == "desc" else order_field.asc()
            query = query.order_by(ordering)
        offset = max(page - 1, 0) * per_page
        policies = list(query.offset(offset).limit(per_page))
        attach_premium(policies)
        return [PolicyRowDTO.from_model(policy) for policy in policies]

    def count(
        self,
        *,
        order_by: Any | None = None,
        order_dir: str = "asc",
        **filters: Any,
    ) -> int:
        column_filters = filters.pop("column_filters", None)
        prepared_filters = self._prepare_column_filters(column_filters)
        order_field = self._resolve_order_field(order_by)
        query = build_policy_query(
            column_filters=prepared_filters,
            order_by=order_field,
            **filters,
        )
        return query.count()

    def mark_deleted(
        self, policy_ids: Sequence[int], *, gateway: DriveGateway | None = None
    ) -> list[int]:
        if not policy_ids:
            return []
        active_ids = [
            row.id
            for row in Policy.select(Policy.id)
            .where((Policy.id.in_(policy_ids)) & (Policy.is_deleted == False))
        ]
        if not active_ids:
            return []
        with db.atomic():
            mark_policies_deleted(list(active_ids), gateway=gateway)
        return active_ids

    def get_policies_by_ids(
        self, policy_ids: Sequence[int], *, as_dto: bool = False
    ) -> dict[int, Policy | PolicyRowDTO]:
        """Получить полисы по списку идентификаторов за один запрос.

        Args:
            policy_ids: Последовательность идентификаторов полисов.
            as_dto: Если ``True``, вернуть DTO вместо моделей.

        Returns:
            dict[int, Policy | PolicyRowDTO]: Словарь ``id -> полис``. Для
            отсутствующих в базе идентификаторов значения отсутствуют.
        """

        if not policy_ids:
            return {}

        unique_ids: list[int] = []
        seen: set[int] = set()
        for policy_id in policy_ids:
            if policy_id is None:
                continue
            try:
                normalized = int(policy_id)
            except (TypeError, ValueError):
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            unique_ids.append(normalized)

        if not unique_ids:
            return {}

        policies = list(Policy.active().where(Policy.id.in_(unique_ids)))
        attach_premium(policies)

        if as_dto:
            return {
                policy.id: PolicyRowDTO.from_model(policy)
                for policy in policies
            }

        return {policy.id: policy for policy in policies}

    def _prepare_column_filters(self, column_filters):
        if not column_filters:
            return None
        prepared: dict[Any, str] = {}
        for key, value in column_filters.items():
            if not value:
                continue
            alias_field = self._FIELD_ALIASES.get(str(key))
            if alias_field is not None:
                prepared[alias_field] = value
            else:
                prepared[str(key)] = value
        return prepared

    def _resolve_order_field(self, order_by: Any | None) -> Field | None:
        if isinstance(order_by, Field):
            if getattr(order_by, "model", None) is None:
                return None
            return order_by
        if isinstance(order_by, str):
            alias_field = self._FIELD_ALIASES.get(order_by)
            if isinstance(alias_field, Field) and getattr(alias_field, "model", None) is not None:
                return alias_field
            candidate = getattr(Policy, order_by, None)
            if isinstance(candidate, Field) and getattr(candidate, "model", None) is not None:
                return candidate
        return Policy.start_date


policy_app_service = PolicyAppService()

__all__ = ["PolicyAppService", "policy_app_service"]
