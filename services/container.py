"""Простейший контейнер зависимостей для сервисов."""

from __future__ import annotations

from functools import lru_cache

from config import get_settings
from infrastructure.drive_gateway import DriveGateway


@lru_cache()
def get_drive_gateway() -> DriveGateway:
    """Получить синглтон-экземпляр адаптера Google Drive."""

    settings = get_settings()
    return DriveGateway(settings)


__all__ = ["get_drive_gateway"]
