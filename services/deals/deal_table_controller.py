"""Контроллер таблицы сделок."""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from database.models import Deal
from services.deal_service import get_deal_by_id, mark_deal_deleted
from ui.base.table_controller import TableController

from .deal_app_service import DealAppService, deal_app_service
from .dto import DealRowDTO

logger = logging.getLogger(__name__)


class DealTableController(TableController):
    """Инкапсулирует загрузку, фильтры и работу фасада сделок."""

    def __init__(self, view, service: DealAppService = deal_app_service):
        self.service = service
        self._pending_total: int | None = None
        super().__init__(
            view,
            model_class=DealRowDTO,
            get_page_func=self._get_page,
            get_total_func=self._get_total,
            filter_func=self._augment_filters,
        )

    # ------------------------------------------------------------------
    # API, используемое представлением
    # ------------------------------------------------------------------
    def delete_deals(self, deals: list[DealRowDTO]) -> None:
        context = getattr(self.view, "_context", None)
        gateway = getattr(context, "drive_gateway", None) if context else None
        for deal in deals:
            mark_deal_deleted(deal.id, gateway=gateway)

    def load_deal(self, deal_id: int) -> Deal | None:
        """Возвращает сделку по идентификатору или ``None``."""

        include_deleted = self.view.is_checked("Показывать удалённые")
        return get_deal_by_id(deal_id, include_deleted=include_deleted)

    def get_statuses(self) -> list[str]:
        return list(self.service.get_statuses())

    # ------------------------------------------------------------------
    # Переопределения TableController
    # ------------------------------------------------------------------
    def set_model_class_and_items(
        self, model_class, items: list[DealRowDTO], total_count: int | None = None
    ) -> None:
        self._apply_items(items, total_count)

    def load_data(self) -> None:  # noqa: PLR0915 - сложность аналогична базовой
        progress = QProgressDialog("Загрузка...", "Отмена", 0, 0, self.view)
        progress.setWindowModality(Qt.WindowModal)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()
        QApplication.processEvents()

        filters = self.get_filters()
        column_filters = filters.get("column_filters")
        logger.debug("column_filters=%s", column_filters)

        sort_field = self.view.COLUMN_FIELD_MAP.get(self.view.current_sort_column)
        if hasattr(sort_field, "name"):
            sort_field = getattr(sort_field, "name")
        if isinstance(sort_field, str):
            order_by = sort_field
        elif sort_field is None:
            order_by = None
        else:
            order_by = getattr(sort_field, "name", None)

        order_dir = (
            "desc"
            if self.view.current_sort_order == Qt.DescendingOrder
            else "asc"
        )

        order_by = self._normalize_order_by(order_by)

        logger.debug("load_data filters=%s sort=%s %s", filters, order_by, order_dir)

        try:
            items, total = self.service.get_page(
                self.view.page,
                self.view.per_page,
                order_by=order_by,
                order_dir=order_dir,
                **filters,
            )
            self._pending_total = total
            logger.debug("loaded %d items of %d", len(items), total)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ошибка при загрузке сделок")
            QMessageBox.critical(self.view, "Ошибка", str(exc))
            progress.close()
            return

        progress.close()
        self._apply_items(items, self._pending_total)

    def _get_page(self, *args: Any, **kwargs: Any) -> list[DealRowDTO]:
        if "order_by" in kwargs:
            kwargs["order_by"] = self._normalize_order_by(kwargs.get("order_by"))

        items, total = self.service.get_page(*args, **kwargs)
        self._pending_total = total
        return items

    def _get_total(self, *args: Any, **kwargs: Any) -> int:
        if self._pending_total is not None:
            total = self._pending_total
            self._pending_total = None
            return total
        return self.service.count(*args, **kwargs)

    def get_distinct_values(self, column_key: str):
        filters = self.get_filters()
        column_filters = dict(filters.get("column_filters") or {})
        column_filters.pop(column_key, None)
        filters["column_filters"] = column_filters
        try:
            return self.service.get_distinct_values(column_key, filters=filters)
        except AttributeError:
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _apply_items(self, items: list[DealRowDTO], total_count: int | None) -> None:
        self.view.update_table(items, total_count)

        if not getattr(self.view, "_settings_loaded", False) and not getattr(
            self.view, "_settings_restore_pending", False
        ):
            self.view._settings_restore_pending = True
            QTimer.singleShot(0, self.view.load_table_settings)

    def _augment_filters(self, filters: dict) -> dict:
        filters = dict(filters)
        filters["show_closed"] = self.view.is_checked("Показать закрытые")
        return filters

    def _normalize_order_by(self, order_by: str | None) -> str | None:
        if order_by == "client":
            return "client_name"
        return order_by
