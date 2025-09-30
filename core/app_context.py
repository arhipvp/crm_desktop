"""Контекст приложения и управление зависимостями."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from config import Settings, get_settings
from infrastructure.drive_gateway import DriveGateway
from infrastructure.sheets_gateway import SheetsGateway
from services.sheets_service import (
    DealCalculationRepository,
    SheetsSyncService,
    TaskRepository,
)

DependencyName = str


class AppContext:
    """Контекст приложения с ленивым созданием зависимостей."""

    _DEPENDENCY_NAMES: ClassVar[set[str]] = {
        "drive_gateway",
        "sheets_gateway",
        "sheets_sync_service",
        "task_repository",
        "deal_calculation_repository",
    }

    def __init__(
        self,
        settings: Settings,
        *,
        drive_gateway_factory: Callable[[Settings], DriveGateway],
        sheets_gateway_factory: Callable[[Settings], SheetsGateway],
        sheets_sync_service_factory: Callable[["AppContext"], SheetsSyncService],
        task_repository_factory: Callable[[], TaskRepository],
        deal_calculation_repository_factory: Callable[[], DealCalculationRepository],
        overrides: dict[str, Any] | None = None,
        instances: dict[str, Any] | None = None,
    ) -> None:
        self._settings = settings
        self._drive_gateway_factory = drive_gateway_factory
        self._sheets_gateway_factory = sheets_gateway_factory
        self._sheets_sync_service_factory = sheets_sync_service_factory
        self._task_repository_factory = task_repository_factory
        self._deal_calculation_repository_factory = (
            deal_calculation_repository_factory
        )
        self._overrides: dict[str, Any] = dict(overrides or {})
        self._instances: dict[str, Any] = dict(instances or {})

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def drive_gateway(self) -> DriveGateway:
        return self._get_dependency(
            "drive_gateway",
            lambda: self._drive_gateway_factory(self._settings),
        )

    @property
    def sheets_gateway(self) -> SheetsGateway:
        return self._get_dependency(
            "sheets_gateway",
            lambda: self._sheets_gateway_factory(self._settings),
        )

    @property
    def task_repository(self) -> TaskRepository:
        return self._get_dependency(
            "task_repository",
            self._task_repository_factory,
        )

    @property
    def deal_calculation_repository(self) -> DealCalculationRepository:
        return self._get_dependency(
            "deal_calculation_repository",
            self._deal_calculation_repository_factory,
        )

    @property
    def sheets_sync_service(self) -> SheetsSyncService:
        return self._get_dependency(
            "sheets_sync_service",
            lambda: self._sheets_sync_service_factory(self),
        )

    def override(self, **deps: Any) -> "AppContext":
        """Создать новый контекст с переопределёнными зависимостями."""

        override_args = dict(deps)
        new_settings = override_args.pop("settings", self._settings)

        unknown = set(override_args) - self._DEPENDENCY_NAMES
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"Неизвестные зависимости для переопределения: {names}")

        overrides = dict(self._overrides)
        overrides.update(override_args)
        if new_settings is self._settings:
            instances = {
                key: value
                for key, value in self._instances.items()
                if key not in override_args
            }
        else:
            instances = {}
        return AppContext(
            settings=new_settings,
            drive_gateway_factory=self._drive_gateway_factory,
            sheets_gateway_factory=self._sheets_gateway_factory,
            sheets_sync_service_factory=self._sheets_sync_service_factory,
            task_repository_factory=self._task_repository_factory,
            deal_calculation_repository_factory=
            self._deal_calculation_repository_factory,
            overrides=overrides,
            instances=instances,
        )

    def _get_dependency(
        self, name: DependencyName, factory: Callable[[], Any]
    ) -> Any:
        if name in self._overrides:
            return self._overrides[name]
        if name not in self._instances:
            self._instances[name] = factory()
        return self._instances[name]


_app_context: AppContext | None = None


def _build_default_context() -> AppContext:
    settings = get_settings()
    return AppContext(
        settings=settings,
        drive_gateway_factory=DriveGateway,
        sheets_gateway_factory=SheetsGateway,
        sheets_sync_service_factory=lambda context: SheetsSyncService(
            settings=context.settings,
            gateway=context.sheets_gateway,
            task_repository=context.task_repository,
            calculation_repository=context.deal_calculation_repository,
        ),
        task_repository_factory=TaskRepository,
        deal_calculation_repository_factory=DealCalculationRepository,
    )


def get_app_context() -> AppContext:
    """Получить (или создать) синглтон контекста приложения."""

    global _app_context
    if _app_context is None:
        _app_context = _build_default_context()
    return _app_context


__all__ = ["AppContext", "get_app_context"]
