import logging
from typing import Any, Callable, Iterable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QProgressDialog, QMessageBox

from ui.base.base_table_model import BaseTableModel
from ui import settings as ui_settings


logger = logging.getLogger(__name__)


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
    def set_model_class_and_items(
        self, model_class, items: list[Any], total_count: int | None = None
    ):
        """Устанавливает модель и обновляет связанные элементы UI."""
        header = self.view.table.horizontalHeader()
        prev_texts = header.get_all_filters() if hasattr(header, "get_all_filters") else []

        self.view.model = BaseTableModel(items, model_class)
        self.view.proxy_model.setSourceModel(self.view.model)
        self.view.table.setModel(self.view.proxy_model)

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
            self.view.data_loaded.emit(self.view.total_count)

        headers = [
            self.view.model.headerData(i, Qt.Horizontal)
            for i in range(self.view.model.columnCount())
        ]
        if hasattr(header, "set_headers"):
            header.set_headers(headers, prev_texts, self.view.COLUMN_FIELD_MAP)
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
        cancelled = False

        def run_task() -> tuple[list, int]:
            items = self.get_page_func(self.view.page, self.view.per_page, **filters)
            total = (
                self.get_total_func(**filters)
                if self.get_total_func
                else len(items)
            )
            return list(items), total

        try:
            items, total = run_task()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ошибка при загрузке данных")
            QMessageBox.critical(self.view, "Ошибка", str(exc))
            progress.close()
            return
        progress.close()
        self.set_model_class_and_items(
            self.model_class, items, total_count=total
        )

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

    def _on_column_filter_changed(self, _column: int, _text: str):
        self.on_filter_changed()
        self.view.save_table_settings()

    def _on_reset_filters(self):
        self.view.filter_controls.clear_all()
        header = self.view.table.horizontalHeader()
        if hasattr(header, "clear_all"):
            header.clear_all()
        ui_settings.set_table_filters(self.view.settings_id, {})
        self.view.save_table_settings()
        self.on_filter_changed()

    # --- Фильтры ---------------------------------------------------------
    def get_column_filters(self) -> dict:
        if not hasattr(self.view, "model") or not self.view.model:
            return {}
        filters: dict = {}
        header = self.view.table.horizontalHeader()
        for visual in range(header.count()):
            logical = header.logicalIndex(visual)
            if header.isSectionHidden(logical):
                continue
            text = (
                header.get_filter_text(visual)
                if hasattr(header, "get_filter_text")
                else ""
            )
            if not text:
                continue
            field = self.view.COLUMN_FIELD_MAP.get(
                logical,
                self.view.model.fields[logical]
                if logical < len(self.view.model.fields)
                else None,
            )
            if field is not None:
                filters[field] = text
        return filters

    def get_filters(self) -> dict:
        filters = {
            "show_deleted": self.view.filter_controls.is_checked(
                "Показывать удалённые"
            ),
            "search_text": self.view.filter_controls.get_search_text(),
            "column_filters": self.get_column_filters(),
        }
        date_range = self.view.filter_controls.get_date_filter()
        if date_range:
            filters.update(date_range)
        if self.filter_func:
            filters = self.filter_func(filters)
        return filters
