from typing import Any

from peewee import Field
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView

from core.app_context import AppContext
from database.models import Executor
from services.executor_service import (
    build_executor_query,
    get_executors_page,
    update_executor,
)
from ui.base.base_table_view import BaseTableView
from ui.base.table_controller import TableController
from ui.common.message_boxes import confirm, show_error
from ui.forms.executor_form import ExecutorForm


class ExecutorTableController(TableController):
    def __init__(
        self,
        view,
        *,
        get_page_func=get_executors_page,
        build_query_func=build_executor_query,
    ) -> None:
        self._get_page_func = get_page_func or get_executors_page
        self._build_query_func = build_query_func or build_executor_query
        super().__init__(
            view,
            model_class=Executor,
            get_page_func=self._get_page,
            get_total_func=self._get_total,
        )

    def _extract_query_params(self, filters: dict[str, Any]) -> dict[str, Any]:
        column_filters = filters.get("column_filters") or {}
        return {
            "search_text": str(filters.get("search_text") or ""),
            "show_inactive": bool(filters.get("show_inactive", True)),
            "column_filters": column_filters,
        }

    def _get_page(
        self,
        page: int,
        per_page: int,
        *,
        order_by: Any | None = None,
        order_dir: str = "asc",
        **filters: Any,
    ):
        params = self._extract_query_params(filters)
        return self._get_page_func(
            page,
            per_page,
            order_by=order_by,
            order_dir=order_dir,
            **params,
        )

    def _get_total(self, **filters: Any) -> int:
        params = self._extract_query_params(filters)
        query = self._build_query_func(**params)
        return query.count()

    def get_distinct_values(
        self, column_key: str, *, column_field: Any | None = None
    ) -> list[dict[str, Any]]:
        filters = dict(self.get_filters())
        column_filters = dict(filters.get("column_filters") or {})
        removed = False
        if column_field is not None and column_field in column_filters:
            column_filters.pop(column_field, None)
            removed = True
        if not removed:
            column_filters.pop(column_key, None)
        filters["column_filters"] = column_filters

        params = self._extract_query_params(filters)
        params["column_filters"] = column_filters
        query = self._build_query_func(**params)

        target_field: Field | None
        if isinstance(column_field, Field):
            target_field = column_field
        elif isinstance(column_field, str):
            target_field = getattr(Executor, column_field, None)
        else:
            target_field = getattr(Executor, column_key, None)

        if target_field is None:
            return []

        values_query = (
            query.select(target_field)
            .where(target_field.is_null(False))
            .distinct()
            .order_by(target_field.asc())
        )

        values = [
            {"value": value, "display": str(value)}
            for (value,) in values_query.tuples()
        ]

        if (
            query.select(target_field)
            .where(target_field.is_null(True))
            .limit(1)
            .exists()
        ):
            values.insert(0, {"value": None, "display": "—"})

        return values


class ExecutorTableView(BaseTableView):
    COLUMN_FIELD_MAP = {
        0: Executor.full_name,
        1: Executor.tg_id,
        2: Executor.is_active,
    }

    def __init__(
        self,
        parent=None,
        *,
        context: AppContext | None = None,
        get_executors_page_func=get_executors_page,
        build_executor_query_func=build_executor_query,
        update_executor_func=update_executor,
    ):
        self._context = context
        self._update_executor = update_executor_func or update_executor
        self.default_sort_column = 0
        self.current_sort_column = self.default_sort_column
        self.current_sort_order = Qt.AscendingOrder

        checkbox_map = {"Показывать неактивных": lambda _state: self.load_data()}
        controller = ExecutorTableController(
            self,
            get_page_func=get_executors_page_func,
            build_query_func=build_executor_query_func,
        )
        super().__init__(
            parent=parent,
            model_class=Executor,
            form_class=ExecutorForm,
            delete_callback=self.delete_selected,
            can_restore=False,
            checkbox_map=checkbox_map,
            controller=controller,
        )
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        # Скрыть нерелевантный чекбокс "Показывать удалённые" для исполнителей
        show_inactive_label = "Показывать неактивных"
        for label, box in self.checkboxes.items():
            if label != show_inactive_label:
                box.setVisible(False)
        self.row_double_clicked.connect(self.edit_selected)
        self.table.horizontalHeader().sortIndicatorChanged.connect(
            self.on_sort_changed
        )
        self.load_data()

    def get_filters(self) -> dict:
        filters = super().get_filters()
        filters.update(
            {
                "show_inactive": self.is_checked("Показывать неактивных"),
            }
        )
        filters.pop("show_deleted", None)
        return filters

    def on_sort_changed(self, column: int, order: Qt.SortOrder):
        self.current_sort_column = column
        self.current_sort_order = order
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
                self._update_executor(executor, is_active=False)
                self.refresh()
            except Exception as e:
                show_error(str(e))
