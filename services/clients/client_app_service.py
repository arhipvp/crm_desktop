"""Прикладной сервис для работы с клиентами на уровне UI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from services.clients.client_service import (
    ClientMergeError,
    DuplicatePhoneError,
    count_clients,
    create_client_from_command,
    delete_clients_by_ids,
    find_similar_clients_dto,
    get_client_detail_dto,
    get_clients_details_by_ids,
    get_clients_page_dto,
    merge_clients_to_dto,
    update_client_from_command,
)
from .dto import (
    ClientCreateCommand,
    ClientDTO,
    ClientDetailsDTO,
    ClientUpdateCommand,
)


class ClientNotFoundError(LookupError):
    """Ошибка отсутствия клиента по запрошенному идентификатору."""


@dataclass
class MergeResult:
    client: ClientDetailsDTO


class ClientAppService:
    """Фасад между UI и доменным уровнем сервисов клиентов."""

    def get_page(
        self,
        page: int,
        per_page: int,
        *,
        order_by: Any | None = None,
        order_dir: str = "asc",
        **filters: Any,
    ) -> list[ClientDTO]:
        order_field = self._normalize_order_field(order_by)
        normalized_order_dir = (order_dir or "").strip().lower()
        if normalized_order_dir not in {"asc", "desc"}:
            normalized_order_dir = "asc"
        return get_clients_page_dto(
            page,
            per_page,
            order_by=order_field,
            order_dir=normalized_order_dir,
            **filters,
        )

    def count(self, *, order_by: Any | None = None, order_dir: str = "asc", **filters: Any) -> int:
        order_field = self._normalize_order_field(order_by)
        normalized_order_dir = (order_dir or "").strip().lower()
        if normalized_order_dir not in {"asc", "desc"}:
            normalized_order_dir = "asc"
        return count_clients(
            order_by=order_field, order_dir=normalized_order_dir, **filters
        )

    def get_detail(self, client_id: int) -> ClientDetailsDTO:
        detail = get_client_detail_dto(client_id)
        if detail is None:
            raise ClientNotFoundError(f"Клиент id={client_id} не найден")
        return detail

    def create(self, command: ClientCreateCommand) -> ClientDetailsDTO:
        return create_client_from_command(command)

    def update(self, command: ClientUpdateCommand) -> ClientDetailsDTO:
        return update_client_from_command(command)

    def delete_many(self, client_ids: Sequence[int]) -> int:
        return delete_clients_by_ids(client_ids)

    def find_similar(self, name: str) -> list[ClientDTO]:
        if not name.strip():
            return []
        return find_similar_clients_dto(name)

    def get_merge_candidates(self, client_ids: Sequence[int]) -> list[ClientDetailsDTO]:
        dtos = get_clients_details_by_ids(client_ids)
        missing = set(client_ids) - {dto.id for dto in dtos}
        if missing:
            missing_str = ", ".join(map(str, sorted(missing)))
            raise ClientMergeError(f"Не найдены клиенты с id: {missing_str}")
        if len(dtos) < 2:
            raise ClientMergeError("Для объединения требуется минимум два клиента")
        return dtos

    def merge(
        self,
        primary_id: int,
        duplicate_ids: Sequence[int],
        updates: dict[str, Any] | None = None,
    ) -> MergeResult:
        client = merge_clients_to_dto(primary_id, duplicate_ids, updates)
        return MergeResult(client=client)

    def _normalize_order_field(self, order_by: Any | None) -> Any:
        if hasattr(order_by, "name"):
            return getattr(order_by, "name")
        return order_by


client_app_service = ClientAppService()

__all__ = [
    "ClientAppService",
    "ClientMergeError",
    "ClientNotFoundError",
    "DuplicatePhoneError",
    "client_app_service",
]
