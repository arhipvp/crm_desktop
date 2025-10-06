from __future__ import annotations

from dataclasses import dataclass, asdict
from types import SimpleNamespace
from typing import Iterable

from database.models import Client


class _FieldStub:
    """Простейший объект поля, имитирующий интерфейс Peewee."""

    def __init__(self, name: str, *, null: bool = True) -> None:
        self.name = name
        self.null = null


def _build_meta(fields: Iterable[str]) -> SimpleNamespace:
    stubs = [_FieldStub(name) for name in fields]
    return SimpleNamespace(sorted_fields=stubs, fields={stub.name: stub for stub in stubs})


@dataclass
class ClientDTO:
    id: int
    name: str
    phone: str | None = None
    email: str | None = None
    is_company: bool = False
    note: str | None = None
    drive_folder_path: str | None = None
    drive_folder_link: str | None = None
    is_deleted: bool = False

    @classmethod
    def from_model(cls, client: Client) -> "ClientDTO":
        return cls(
            id=client.id,
            name=client.name,
            phone=client.phone,
            email=client.email,
            is_company=client.is_company,
            note=client.note,
            drive_folder_path=client.drive_folder_path,
            drive_folder_link=client.drive_folder_link,
            is_deleted=client.is_deleted,
        )


CLIENT_TABLE_FIELDS = [
    "id",
    "name",
    "phone",
    "email",
    "is_company",
    "note",
    "drive_folder_path",
    "drive_folder_link",
    "is_deleted",
]

ClientDTO._meta = _build_meta(CLIENT_TABLE_FIELDS)  # type: ignore[attr-defined]


@dataclass
class ClientDetailsDTO(ClientDTO):
    deals_count: int = 0
    policies_count: int = 0

    @classmethod
    def from_model(cls, client: Client) -> "ClientDetailsDTO":
        deals_count = getattr(client, "_deals_count", None)
        if deals_count is None:
            deals_count = client.deals.count()

        policies_count = getattr(client, "_policies_count", None)
        if policies_count is None:
            policies_count = client.policies.count()
        return cls(
            id=client.id,
            name=client.name,
            phone=client.phone,
            email=client.email,
            is_company=client.is_company,
            note=client.note,
            drive_folder_path=client.drive_folder_path,
            drive_folder_link=client.drive_folder_link,
            is_deleted=client.is_deleted,
            deals_count=deals_count,
            policies_count=policies_count,
        )


ClientDetailsDTO._meta = _build_meta(
    CLIENT_TABLE_FIELDS + ["deals_count", "policies_count"]
)  # type: ignore[attr-defined]


@dataclass(frozen=True)
class ClientCreateCommand:
    name: str
    phone: str | None = None
    email: str | None = None
    is_company: bool = False
    note: str | None = None

    def to_payload(self) -> dict:
        payload: dict[str, object] = {}
        for key, value in asdict(self).items():
            if value in (None, ""):
                continue
            payload[key] = value
        return payload


@dataclass(frozen=True)
class ClientUpdateCommand:
    id: int
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    is_company: bool | None = None
    note: str | None = None
    is_active: bool | None = None

    def to_payload(self) -> dict:
        payload: dict[str, object] = {}
        for key, value in asdict(self).items():
            if key == "id":
                continue
            if value in (None, ""):
                continue
            payload[key] = value
        return payload

