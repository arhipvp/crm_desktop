from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Iterable

from database.models import Client, Deal, Policy


class _FieldStub:
    """Простейший объект поля, имитирующий интерфейс Peewee."""

    def __init__(self, name: str, *, null: bool = True) -> None:
        self.name = name
        self.null = null


def _build_meta(fields: Iterable[str]) -> SimpleNamespace:
    stubs = [_FieldStub(name) for name in fields]
    return SimpleNamespace(sorted_fields=stubs, fields={stub.name: stub for stub in stubs})


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
    "id",
    "client_id",
    "client_name",
    "deal_id",
    "deal_description",
    "policy_number",
    "insurance_type",
    "insurance_company",
    "contractor",
    "sales_channel",
    "start_date",
    "end_date",
    "vehicle_brand",
    "vehicle_model",
    "vehicle_vin",
    "note",
    "drive_folder_link",
    "renewed_to",
    "premium",
    "is_deleted",
]

PolicyRowDTO._meta = _build_meta(POLICY_TABLE_FIELDS)  # type: ignore[attr-defined]

__all__ = [
    "PolicyRowDTO",
    "PolicyClientInfo",
    "PolicyDealInfo",
]
