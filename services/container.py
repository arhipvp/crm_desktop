"""Простейший контейнер зависимостей для сервисов."""

from __future__ import annotations

from functools import lru_cache

from config import get_settings
from infrastructure.drive_gateway import DriveGateway
from infrastructure.sheets_gateway import SheetsGateway
from services.sheets_service import (
    DealCalculationRepository,
    SheetsSyncService,
    TaskRepository,
)


@lru_cache()
def get_drive_gateway() -> DriveGateway:
    """Получить синглтон-экземпляр адаптера Google Drive."""

    settings = get_settings()
    return DriveGateway(settings)


@lru_cache()
def get_sheets_gateway() -> SheetsGateway:
    settings = get_settings()
    return SheetsGateway(settings)


@lru_cache()
def get_task_repository() -> TaskRepository:
    return TaskRepository()


@lru_cache()
def get_deal_calculation_repository() -> DealCalculationRepository:
    return DealCalculationRepository()


@lru_cache()
def get_sheets_sync_service() -> SheetsSyncService:
    settings = get_settings()
    return SheetsSyncService(
        settings=settings,
        gateway=get_sheets_gateway(),
        task_repository=get_task_repository(),
        calculation_repository=get_deal_calculation_repository(),
    )


__all__ = [
    "get_drive_gateway",
    "get_sheets_gateway",
    "get_task_repository",
    "get_deal_calculation_repository",
    "get_sheets_sync_service",
]
