import logging
from collections.abc import Iterable as IterableABC

from typing import Any, Callable, Iterable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QProgressDialog, QMessageBox

from ui.base.base_table_model import BaseTableModel


logger = logging.getLogger(__name__)


def _normalize_filter_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, IterableABC):
        result: list[str] = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, str):
                text = item.strip()
            else:
                text = str(item).strip()
            if text:
                result.append(text)
        return result
    text = str(value).strip()
    return [text] if text else []


class TableController:
    """Контроллер таблицы: загрузка данных, пагинация и фильтрация."""

    def __init__(
        self,
        view,
        *,
        model_class: Any | None = None,
        get_page_func: Callable[..., Iterable[Any]] | None = None,
        get_total_func: Callable[..., int] | None = None,
        filter_func: Callable[[dict], dict] | None = None,
    ):
        self.view = view
        self.model_class = model_class
        self.get_page_func = get_page_func
        self.get_total_func = get_total_func
        self.filter_func = filter_func

    # --- Работа с моделью -------------------------------------------------
    def _create_table_model(self, items: Iterable[Any], model_class: Any) -> BaseTableModel:
        """Создаёт таблицу по умолчанию для контроллера."""

        if not isinstance(items, list):
            items = list(items)
        return BaseTableModel(items, model_class)

    def set_model_class_and_items(
        self, model_class, items: list[Any], total_count: int | None = None
    ):
        """Устанавливает модель и обновляет связанные элементы UI."""
        self.view.model = self._create_table_model(items, model_class)
        self.view.proxy.setSourceModel(self.view.model)
        self.view.table.setModel(self.view.proxy)
        self.view.apply_saved_filters()
        if getattr(self.view, "_settings_loaded", False):
            self.view.save_table_settings()

        try:
            self.view.table.sortByColumn(
                self.view.current_sort_column, self.view.current_sort_order
            )
            self.view.table.resizeColumnsToContents()
        except NotImplementedError:
            pass

        if total_count is not None:
            self.view.total_count = total_count
            self.view.paginator.update(
                self.view.total_count, self.view.page, self.view.per_page
            )
        self.view.data_loaded.emit(self.view.proxy.rowCount())

        if not getattr(self.view, "_settings_loaded", False) and not getattr(
            self.view, "_settings_restore_pending", False
        ):
            self.view._settings_restore_pending = True
            QTimer.singleShot(0, self.view.load_table_settings)

    # --- Загрузка данных --------------------------------------------------
    def load_data(self):
        if not self.model_class or not self.get_page_func:
            return

        progress = QProgressDialog("Загрузка...", "Отмена", 0, 0, self.view)
        progress.setWindowModality(Qt.WindowModal)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()
        QApplication.processEvents()

        filters = self.get_filters()
        column_filters = filters.get("column_filters")
        logger.debug("column_filters=%s", column_filters)

        sort_field = self.view.COLUMN_FIELD_MAP.get(
            self.view.current_sort_column
        )
        if sort_field is None:
            model_fields: list[Any] = []
            model = getattr(self.view, "model", None)
            if model is not None:
                model_fields = getattr(model, "fields", [])
            elif self.model_class is not None:
                try:
                    model_fields = BaseTableModel([], self.model_class).fields
                except Exception:  # noqa: BLE001 - best effort fallback
                    model_fields = []
            index = self.view.current_sort_column
            if model_fields and 0 <= index < len(model_fields):
                sort_field = model_fields[index]

        order_dir = (
            "desc"
            if self.view.current_sort_order == Qt.DescendingOrder
            else "asc"
        )

        logger.debug("load_data filters=%s sort=%s %s", filters, sort_field, order_dir)

        def run_task() -> tuple[list, int]:
            items = self.get_page_func(
                self.view.page,
                self.view.per_page,
                order_by=sort_field,
                order_dir=order_dir,
                **filters,
            )
            total = (
                self.get_total_func(
                    order_by=sort_field,
                    order_dir=order_dir,
                    **filters,
                )
                if self.get_total_func
                else len(items)
            )
            return list(items), total

        try:
            items, total = run_task()
            logger.debug("loaded %d items of %d", len(items), total)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ошибка при загрузке данных")
            QMessageBox.critical(self.view, "Ошибка", str(exc))
            progress.close()
            return
        progress.close()
        if getattr(self.view, "model", None) is None:
            self.set_model_class_and_items(
                self.model_class, items, total_count=total
            )
            return

        self.view.model = self._create_table_model(items, self.model_class)
        self.view.proxy.setSourceModel(self.view.model)
        self.view.table.setModel(self.view.proxy)
        self.view.apply_saved_filters()
        self.view.save_table_settings()
        try:
            self.view.table.sortByColumn(
                self.view.current_sort_column, self.view.current_sort_order
            )
        except NotImplementedError:
            pass
        if total is not None:
            self.view.total_count = total
            self.view.paginator.update(
                self.view.total_count, self.view.page, self.view.per_page
            )
        self.view.data_loaded.emit(self.view.proxy.rowCount())

    def refresh(self):
        self.load_data()

    def on_filter_changed(self, *args, **kwargs):
        self.view.page = 1
        self.load_data()

    def next_page(self):
        self.view.page += 1
        self.load_data()

    def prev_page(self):
        if self.view.page > 1:
            self.view.page -= 1
            self.load_data()

    def _on_per_page_changed(self, per_page: int):
        self.view.per_page = per_page
        self.view.page = 1
        self.view.save_table_settings()
        self.load_data()

    def _on_reset_filters(self):
        self.view.clear_filters()
        self.view.clear_column_filters()
        self.view.save_table_settings()
        self.on_filter_changed()

    # --- Фильтры ---------------------------------------------------------
    def get_filters(self) -> dict:
        filters = {
            "show_deleted": self.view.is_checked("Показывать удалённые"),
            "search_text": self.view.get_search_text(),
        }
        header = self.view.table.horizontalHeader()
        column_filters = {}
        for logical, state in self.view._column_filters.items():
            visual = header.visualIndex(logical)
            if visual < 0:
                continue
            logical_index = header.logicalIndex(visual)
            if logical_index < 0 or header.isSectionHidden(logical_index):
                continue
            field = self.view.COLUMN_FIELD_MAP.get(logical_index)
            if not field:
                continue
            backend_value = state.backend_value() if state else None
            values = _normalize_filter_values(backend_value)
            if not values:
                continue
            column_filters[field] = values
        filters["column_filters"] = column_filters
        date_range = self.view.get_date_filter()
        if date_range:
            filters.update(date_range)
        if self.filter_func:
            filters = self.filter_func(filters)
        return filters

    # --- Значения --------------------------------------------------------
    def get_distinct_values(self, column_key: str) -> list[Any] | None:
        """Возвращает список уникальных значений для столбца.

        Базовая реализация не имеет доступа к данным и возвращает ``None``.
        Потомки могут переопределить метод для работы с сервисами/репозиториями.
        """

        return None
