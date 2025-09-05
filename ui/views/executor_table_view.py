from PySide6.QtCore import Qt
from ui.base.base_table_view import BaseTableView
from database.models import Executor
from ui.forms.executor_form import ExecutorForm
from services.executor_service import (
    build_executor_query,
    get_executors_page,
    update_executor,
)
from ui.common.message_boxes import confirm, show_error


class ExecutorTableView(BaseTableView):
    COLUMN_FIELD_MAP = {
        0: Executor.full_name,
        1: Executor.tg_id,
        2: Executor.is_active,
    }

    def __init__(self, parent=None):
        self.order_by = Executor.full_name
        self.order_dir = "asc"
        self.default_sort_column = 0
        self.current_sort_column = self.default_sort_column
        self.current_sort_order = Qt.AscendingOrder

        checkbox_map = {"Показывать неактивных": self.refresh}
        super().__init__(
            parent=parent,
            model_class=Executor,
            form_class=ExecutorForm,
            delete_callback=self.delete_selected,
            can_restore=False,
            checkbox_map=checkbox_map,
        )
        # Скрыть нерелевантный чекбокс "Показывать удалённые" для исполнителей
        try:
            show_inactive_label = "�?�?������<�?���'�? �?�����'��?�?�<�:"
            cbx = getattr(self.filter_controls, "_cbx", None)
            if cbx:
                for label, box in cbx.checkboxes.items():
                    if label != show_inactive_label:
                        box.setVisible(False)
        except Exception:
            pass
        self.row_double_clicked.connect(self.edit_selected)
        self.table.horizontalHeader().sortIndicatorChanged.connect(
            self.on_sort_changed
        )
        self.load_data()

    # Ensure search/filters/pagination use local loader (not TableController)
    def refresh(self):
        self.load_data()

    def on_filter_changed(self, *args, **kwargs):
        self.page = 1
        self.load_data()

    def next_page(self):
        self.page += 1
        self.load_data()

    def prev_page(self):
        if self.page > 1:
            self.page -= 1
            self.load_data()

    def _on_per_page_changed(self, per_page: int):
        self.per_page = per_page
        self.page = 1
        try:
            self.save_table_settings()
        except Exception:
            pass
        self.load_data()

    def _on_column_filter_changed(self, column: int, text: str):
        self.on_filter_changed()
        try:
            self.save_table_settings()
        except Exception:
            pass

    def get_filters(self) -> dict:
        filters = super().get_filters()
        filters.update(
            {
                "show_inactive": self.filter_controls.is_checked("Показывать неактивных"),
            }
        )
        filters.pop("show_deleted", None)
        return filters

    def load_data(self):
        filters = self.get_filters()
        items = get_executors_page(
            self.page,
            self.per_page,
            order_by=self.order_by,
            order_dir=self.order_dir,
            **filters,
        )
        total = build_executor_query(**filters).count()
        self.set_model_class_and_items(Executor, list(items), total_count=total)

    def on_sort_changed(self, column: int, order: Qt.SortOrder):
        self.current_sort_column = column
        self.current_sort_order = order
        field = self.COLUMN_FIELD_MAP.get(column)
        if field is None:
            return
        self.order_dir = "desc" if order == Qt.DescendingOrder else "asc"
        self.order_by = field
        self.page = 1
        self.load_data()

    def get_selected(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self.model.get_item(self._source_row(idx))

    def delete_selected(self):
        executor = self.get_selected()
        if executor and confirm(f"Деактивировать {executor.full_name}?"):
            try:
                update_executor(executor, is_active=False)
                self.refresh()
            except Exception as e:
                show_error(str(e))
