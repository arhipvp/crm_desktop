"""Подмодуль сервисов, связанных со сделками."""

from .deal_app_service import DealAppService, deal_app_service
from .deal_table_controller import DealTableController
from .dto import DealRowDTO, DealClientInfo, DealExecutorInfo

__all__ = [
    "DealAppService",
    "DealTableController",
    "deal_app_service",
    "DealRowDTO",
    "DealClientInfo",
    "DealExecutorInfo",
]
