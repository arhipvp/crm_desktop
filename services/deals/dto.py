"""DTO для представления строк таблицы сделок."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace
from typing import Iterable, Optional

from database.models import Client, Deal, Executor

__all__ = [
    "DealClientInfo",
    "DealExecutorInfo",
    "DealRowDTO",
    "deal_to_row_dto",
    "deals_to_row_dtos",
]


class _FieldStub:
    """Простейший объект поля, имитирующий интерфейс Peewee."""

    def __init__(self, name: str, *, null: bool = True) -> None:
        self.name = name
        self.null = null


def _build_meta(fields: Iterable[str]) -> SimpleNamespace:
    stubs = [_FieldStub(name) for name in fields]
    return SimpleNamespace(sorted_fields=stubs, fields={stub.name: stub for stub in stubs})


@dataclass(slots=True)
class DealClientInfo:
    """Информация о клиенте сделки."""

    id: int
    name: str


@dataclass(slots=True)
class DealExecutorInfo:
    """Информация об исполнителе сделки."""

    id: int
    full_name: str


@dataclass
class DealRowDTO:
    """Данные для отображения строки таблицы сделок."""

    id: int
    reminder_date: Optional[date]
    client: DealClientInfo
    status: Optional[str]
    description: str
    calculations: Optional[str]
    start_date: date
    is_closed: bool
    closed_reason: Optional[str]
    drive_folder_path: Optional[str]
    drive_folder_link: Optional[str]
    is_deleted: bool
    executor: Optional[DealExecutorInfo] = None

    @property
    def client_id(self) -> int:
        return self.client.id


DEAL_TABLE_FIELDS = [
    "id",
    "reminder_date",
    "client",
    "status",
    "description",
    "calculations",
    "start_date",
    "is_closed",
    "closed_reason",
    "drive_folder_path",
    "drive_folder_link",
    "is_deleted",
]

DealRowDTO._meta = _build_meta(DEAL_TABLE_FIELDS)  # type: ignore[attr-defined]


def _to_client_info(client: Client | None, client_id: int) -> DealClientInfo:
    if client is None:
        return DealClientInfo(id=client_id, name="—")
    return DealClientInfo(id=client.id, name=client.name)


def _to_executor_info(executor: Executor | None) -> DealExecutorInfo | None:
    if executor is None:
        return None
    return DealExecutorInfo(id=executor.id, full_name=executor.full_name)


def deal_to_row_dto(deal: Deal) -> DealRowDTO:
    client_info = _to_client_info(getattr(deal, "client", None), deal.client_id)
    executor = getattr(deal, "_executor", None)
    executor_info = _to_executor_info(executor)
    return DealRowDTO(
        id=deal.id,
        reminder_date=deal.reminder_date,
        client=client_info,
        status=deal.status,
        description=deal.description,
        calculations=deal.calculations,
        start_date=deal.start_date,
        is_closed=deal.is_closed,
        closed_reason=deal.closed_reason,
        drive_folder_path=deal.drive_folder_path,
        drive_folder_link=deal.drive_folder_link,
        is_deleted=deal.is_deleted,
        executor=executor_info,
    )


def deals_to_row_dtos(deals: Iterable[Deal]) -> list[DealRowDTO]:
    return [deal_to_row_dto(deal) for deal in deals]
