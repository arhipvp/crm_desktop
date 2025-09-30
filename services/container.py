"""Простейший контейнер зависимостей для сервисов."""

from __future__ import annotations

from core.app_context import get_app_context
from infrastructure.drive_gateway import DriveGateway
from infrastructure.sheets_gateway import SheetsGateway
from services.sheets_service import (
    DealCalculationRepository,
    SheetsSyncService,
    TaskRepository,
)


def get_drive_gateway() -> DriveGateway:
    """Получить синглтон-экземпляр адаптера Google Drive."""

    return get_app_context().drive_gateway


def get_sheets_gateway() -> SheetsGateway:
    return get_app_context().sheets_gateway


def get_task_repository() -> TaskRepository:
    return get_app_context().task_repository


def get_deal_calculation_repository() -> DealCalculationRepository:
    return get_app_context().deal_calculation_repository


def get_sheets_sync_service() -> SheetsSyncService:
    return get_app_context().sheets_sync_service


__all__ = [
    "get_app_context",
    "get_drive_gateway",
    "get_sheets_gateway",
    "get_task_repository",
    "get_deal_calculation_repository",
    "get_sheets_sync_service",
]
