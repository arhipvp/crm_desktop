from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Callable, Iterable

from peewee import CharField, DecimalField, Field, IntegerField, TextField

from database.models import Client, Deal, Policy


_EXTRA_FIELD_FACTORIES: dict[str, Callable[[], Field]] = {
    "client_id": lambda: IntegerField(null=True),
    "client_name": lambda: CharField(null=True),
    "deal_id": lambda: IntegerField(null=True),
    "deal_description": lambda: TextField(null=True),
    "premium": lambda: DecimalField(null=True, max_digits=12, decimal_places=2),
}


def _resolve_policy_field(name: str) -> Field:
    """Вернуть peewee-поле для указанного имени столбца таблицы полисов."""

    meta = Policy._meta
    primary_key = meta.primary_key
    if primary_key is not None and name == primary_key.name:
        return primary_key
    existing = meta.fields.get(name)
    if isinstance(existing, Field):
        return existing
    factory = _EXTRA_FIELD_FACTORIES.get(name)
    if factory is not None:
        field = factory()
    else:
        field = CharField(null=True)
    field.name = name
    # ``column_name`` используется при экспорте CSV, поэтому задаём его явно.
    field.column_name = name  # type: ignore[attr-defined]
    return field


def _build_meta(fields: Iterable[str | Field]) -> SimpleNamespace:
    resolved: list[Field] = []
    for item in fields:
        field = item if isinstance(item, Field) else _resolve_policy_field(item)
        if not getattr(field, "name", None):
            # На всякий случай синхронизируем имя с исходным значением.
            field.name = str(item)
        resolved.append(field)
    return SimpleNamespace(sorted_fields=resolved, fields={f.name: f for f in resolved})


@dataclass(slots=True, frozen=True)
class PolicyClientInfo:
    """Минимальное представление клиента, связанного с полисом."""

    id: int | None
    name: str
    phone: str | None = None
    email: str | None = None


@dataclass(slots=True, frozen=True)
class PolicyDealInfo:
    """Минимальное представление сделки, связанной с полисом."""

    id: int | None
    description: str | None = None


@dataclass(slots=True)
class PolicyRowDTO:
    """Строка таблицы полисов, адаптированная под `BaseTableModel`."""

    id: int
    client_id: int | None
    client_name: str
    deal_id: int | None
    deal_description: str | None
    policy_number: str | None
    insurance_type: str | None = None
    insurance_company: str | None = None
    contractor: str | None = None
    sales_channel: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    vehicle_brand: str | None = None
    vehicle_model: str | None = None
    vehicle_vin: str | None = None
    note: str | None = None
    drive_folder_link: str | None = None
    renewed_to: str | None = None
    premium: Decimal = Decimal("0")
    is_deleted: bool = False
    client: PolicyClientInfo | None = field(default=None, repr=False)
    deal: PolicyDealInfo | None = field(default=None, repr=False)

    @classmethod
    def from_model(cls, policy: Policy) -> "PolicyRowDTO":
        client: Client | None = getattr(policy, "client", None)
        deal: Deal | None = getattr(policy, "deal", None)
        client_info = None
        if client is not None:
            client_info = PolicyClientInfo(
                id=getattr(client, "id", None),
                name=getattr(client, "name", ""),
                phone=getattr(client, "phone", None),
                email=getattr(client, "email", None),
            )
        deal_info = None
        if deal is not None:
            deal_info = PolicyDealInfo(
                id=getattr(deal, "id", None),
                description=getattr(deal, "description", None),
            )
        premium_value = getattr(policy, "_premium", Decimal("0"))
        if not isinstance(premium_value, Decimal):
            premium_value = Decimal(str(premium_value or 0))
        return cls(
            id=policy.id,
            client_id=policy.client_id,
            client_name=client.name if client is not None else "",
            deal_id=policy.deal_id,
            deal_description=deal.description if deal is not None else None,
            policy_number=policy.policy_number,
            insurance_type=policy.insurance_type,
            insurance_company=policy.insurance_company,
            contractor=policy.contractor,
            sales_channel=policy.sales_channel,
            start_date=policy.start_date,
            end_date=policy.end_date,
            vehicle_brand=policy.vehicle_brand,
            vehicle_model=policy.vehicle_model,
            vehicle_vin=policy.vehicle_vin,
            note=policy.note,
            drive_folder_link=policy.drive_folder_link,
            renewed_to=policy.renewed_to,
            premium=premium_value,
            is_deleted=policy.is_deleted,
            client=client_info,
            deal=deal_info,
        )


POLICY_TABLE_FIELDS = [
    Policy._meta.primary_key,
    "client_name",
    "deal_description",
    Policy.policy_number,
    Policy.insurance_type,
    Policy.insurance_company,
    Policy.contractor,
    Policy.sales_channel,
    Policy.start_date,
    Policy.end_date,
    Policy.vehicle_brand,
    Policy.vehicle_model,
    Policy.vehicle_vin,
    Policy.note,
    Policy.drive_folder_link,
    Policy.renewed_to,
    "premium",
    Policy.is_deleted,
]

PolicyRowDTO._meta = _build_meta(POLICY_TABLE_FIELDS)  # type: ignore[attr-defined]

__all__ = [
    "PolicyRowDTO",
    "PolicyClientInfo",
    "PolicyDealInfo",
]
