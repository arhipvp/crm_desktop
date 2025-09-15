import logging
from typing import Any, Callable, Iterable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QProgressDialog, QMessageBox

from ui.base.base_table_model import BaseTableModel


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
        self.view.model = BaseTableModel(items, model_class)
        self.view.proxy.setSourceModel(self.view.model)
        self.view.table.setModel(self.view.proxy)

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
        if getattr(self.view, "model", None) is None:
            self.set_model_class_and_items(
                self.model_class, items, total_count=total
            )
            return

        self.view.model = BaseTableModel(items, self.model_class)
        self.view.proxy.setSourceModel(self.view.model)
        self.view.table.setModel(self.view.proxy)
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
        self.view.filter_controls.clear_all()
        if hasattr(self.view, "clear_header_filters"):
            self.view.clear_header_filters()
        self.view.save_table_settings()
        self.on_filter_changed()

    # --- Фильтры ---------------------------------------------------------
    def get_filters(self) -> dict:
        filters = {
            "show_deleted": self.view.filter_controls.is_checked(
                "Показывать удалённые"
            ),
            "search_text": self.view.filter_controls.get_search_text(),
        }
        date_range = self.view.filter_controls.get_date_filter()
        if date_range:
            filters.update(date_range)
        if self.filter_func:
            filters = self.filter_func(filters)
        return filters
