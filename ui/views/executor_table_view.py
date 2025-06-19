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
    def __init__(self, parent=None):
        checkbox_map = {"Показывать неактивных": self.refresh}
        super().__init__(
            parent=parent,
            model_class=Executor,
            form_class=ExecutorForm,
            checkbox_map=checkbox_map,
        )
        self.row_double_clicked.connect(self.edit_selected)
        self.load_data()

    def get_filters(self) -> dict:
        return {
            "search_text": self.filter_controls.get_search_text(),
            "show_inactive": self.filter_controls.is_checked("Показывать неактивных"),
        }

    def load_data(self):
        filters = self.get_filters()
        items = get_executors_page(self.page, self.per_page, **filters)
        total = build_executor_query(**filters).count()
        self.set_model_class_and_items(Executor, list(items), total_count=total)

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
