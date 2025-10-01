"""Представление таблицы сделок, работающее через контроллер и DTO."""

from __future__ import annotations

import logging
from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QHBoxLayout, QLineEdit

from core.app_context import AppContext
from services import deal_journal
from services.deals.deal_table_controller import DealTableController
from services.deals.dto import DealRowDTO
from ui.base.base_table_model import BaseTableModel
from ui.base.base_table_view import BaseTableView
from ui.common.message_boxes import confirm, show_error
from ui.forms.deal_form import DealForm
from ui.views.deal_detail import DealDetailView

logger = logging.getLogger(__name__)


class DealTableModel(BaseTableModel):
    """Модель таблицы, работающая поверх DTO и не зависящая от Peewee."""

    def __init__(
        self,
        objects: Iterable[DealRowDTO],
        parent=None,
        *,
        deal_journal_module=deal_journal,
    ) -> None:
        super().__init__(list(objects), DealRowDTO, parent)
        self._deal_journal = deal_journal_module or deal_journal
        self._all_objects = list(self.objects)

        # скрываем ссылку на папку и переносим поля закрытия в конец
        self.fields = [f for f in self.fields if f.name != "drive_folder_link"]

        def move_to_end(field_name: str) -> None:
            for index, field in enumerate(self.fields):
                if field.name == field_name:
                    self.fields.append(self.fields.pop(index))
                    break

        move_to_end("is_closed")
        move_to_end("closed_reason")

        self.headers = [f.name for f in self.fields]
        self.virtual_fields = ["executor"]
        self.headers.append("Исполнитель")

        self._quick_text = ""
        self._quick_status: str | None = None

    def columnCount(self, parent=None):  # type: ignore[override]
        return len(self.fields) + len(self.virtual_fields)

    def data(self, index, role=Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None

        obj: DealRowDTO = self.objects[index.row()]
        if role == Qt.FontRole and getattr(obj, "is_deleted", False):
            font = QFont()
            font.setStrikeOut(True)
            return font
        if role == Qt.ForegroundRole and obj.executor is not None:
            return QColor("red")

        column = index.column()
        if column >= len(self.fields):
            if role == Qt.DisplayRole:
                executor = obj.executor
                return executor.full_name if executor else "—"
            return None

        field = self.fields[column]
        if field.name == "client" and role == Qt.DisplayRole:
            return obj.client.name if obj.client else "—"

        if field.name == "calculations" and role in {Qt.DisplayRole, Qt.ToolTipRole}:
            formatted = self._deal_journal.format_for_display(
                getattr(obj, field.name), active_only=True
            )
            if role == Qt.DisplayRole:
                return self.shorten_text(formatted) if formatted else "—"
            return formatted or None

        return super().data(index, role)

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # type: ignore[override]
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        if section < len(self.fields):
            return super().headerData(section, orientation, role)
        return self.headers[-1]

    # --- Быстрый фильтр -------------------------------------------------
    def apply_quick_filter(self, text: str = "", status: str | None = None) -> None:
        self._quick_text = text.lower()
        self._quick_status = status

        def matches(obj: DealRowDTO) -> bool:
            if self._quick_text:
                vin_text = " ".join(getattr(obj, "policy_vins", ()))
                haystack = " ".join(
                    [
                        obj.client.name,
                        obj.description or "",
                        obj.status or "",
                        vin_text,
                    ]
                ).lower()
                if self._quick_text not in haystack:
                    return False
            if self._quick_status:
                if (obj.status or "") != self._quick_status:
                    return False
            return True

        self.objects = [obj for obj in self._all_objects if matches(obj)]
        self.layoutChanged.emit()


class DealTableView(BaseTableView):
    COLUMN_FIELD_MAP = {
        0: "reminder_date",
        1: "client",
        2: "status",
        3: "description",
        4: "calculations",
        5: "start_date",
        6: "is_closed",
        7: "closed_reason",
        8: "executor",
    }

    def __init__(
        self,
        parent=None,
        *,
        context: AppContext | None = None,
        controller: DealTableController | None = None,
        deal_journal_module=deal_journal,
    ) -> None:
        self._context = context
        self._deal_journal = deal_journal_module or deal_journal
        controller = controller or DealTableController(self)

        checkboxes = {
            "Показывать удалённые": self.on_filter_changed,
            "Показать закрытые": self.on_filter_changed,
        }
        super().__init__(
            parent=parent,
            form_class=DealForm,
            detail_view_class=DealDetailView,
            controller=controller,
            checkbox_map=checkboxes,
        )
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # быстрый фильтр по строке и статусу
        self.quick_filter_edit = QLineEdit()
        self.quick_filter_edit.setPlaceholderText("Поиск...")
        self.status_filter = QComboBox()
        self.status_filter.addItem("Все", None)
        for status in controller.get_statuses():
            self.status_filter.addItem(status, status)

        quick_layout = QHBoxLayout()
        quick_layout.addWidget(self.quick_filter_edit)
        quick_layout.addWidget(self.status_filter)

        index = self.left_layout.indexOf(self.table)
        self.left_layout.insertLayout(index, quick_layout)

        self.quick_filter_edit.textChanged.connect(self.apply_quick_filter)
        self.status_filter.currentIndexChanged.connect(self.apply_quick_filter)

        self.table.horizontalHeader().sortIndicatorChanged.connect(
            self.on_sort_changed
        )
        self.row_double_clicked.connect(self.open_detail)

        QShortcut("Return", self.table, activated=self.open_detail)
        QShortcut("Ctrl+E", self.table, activated=self.edit_selected)
        QShortcut("Delete", self.table, activated=self.delete_selected)
        QShortcut("Ctrl+D", self.table, activated=self.duplicate_selected)

        self.load_data()

    # ------------------------------------------------------------------
    # Работа с моделью
    # ------------------------------------------------------------------
    def update_table(self, items: list[DealRowDTO], total_count: int | None) -> None:
        self.model = DealTableModel(items, deal_journal_module=self._deal_journal)
        self.proxy.setSourceModel(self.model)
        self.table.setModel(self.proxy)

        try:
            self.table.sortByColumn(
                self.current_sort_column, self.current_sort_order
            )
            self.table.resizeColumnsToContents()
        except NotImplementedError:
            pass

        if total_count is not None:
            self.total_count = total_count
            self.paginator.update(self.total_count, self.page, self.per_page)
            self.data_loaded.emit(self.total_count)

        self.table.horizontalHeader().setSortIndicator(
            self.current_sort_column, self.current_sort_order
        )
        self.apply_quick_filter()

    # ------------------------------------------------------------------
    # Работа с элементами управления
    # ------------------------------------------------------------------
    def get_selected(self) -> DealRowDTO | None:
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        source_row = self.proxy.mapToSource(index).row()
        return self.model.get_item(source_row)

    def delete_selected(self) -> None:
        deal = self.get_selected()
        if not deal:
            return
        if not confirm(f"Удалить сделку {deal.description}?"):
            return
        try:
            self.controller.delete_deals([deal])
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            show_error(str(exc))

    def add_new(self):
        form = DealForm(context=self._context)
        if form.exec():
            self.refresh()

    def duplicate_selected(self, _=None):
        dto = self.get_selected()
        if not dto:
            return
        instance = self._load_deal_instance(dto.id)
        if instance is None:
            return
        form = DealForm(context=self._context)
        form.fill_from_obj(instance)
        if "is_closed" in form.fields:
            form.fields["is_closed"].setChecked(False)
        if "closed_reason" in form.fields:
            form.fields["closed_reason"].setText("")
        if form.exec():
            self.refresh()
            if form.instance:
                dlg = DealDetailView(
                    form.instance, parent=self, context=self._context
                )
                dlg.exec()

    def edit_selected(self, _=None):
        self.edit_selected_default()

    def edit_selected_default(self) -> None:
        dto = self.get_selected()
        if not dto:
            return

        instance = self._load_deal_instance(dto.id)
        if instance is None:
            return

        if self.detail_view_class:
            kwargs = {"parent": self}
            if getattr(self, "_context", None) is not None:
                kwargs["context"] = self._context
            try:
                dlg = self.detail_view_class(instance, **kwargs)
            except TypeError:
                kwargs.pop("context", None)
                dlg = self.detail_view_class(instance, **kwargs)
            dlg.exec()
            self.refresh()
            return

        if self.form_class:
            form_kwargs = {"parent": self}
            if getattr(self, "_context", None) is not None:
                form_kwargs["context"] = self._context
            try:
                form = self.form_class(instance, **form_kwargs)
            except TypeError:
                form_kwargs.pop("context", None)
                form = self.form_class(instance, **form_kwargs)
            if form.exec():
                self.refresh()

    def open_detail(self, _=None):
        dto = self.get_selected()
        if not dto:
            return
        instance = self._load_deal_instance(dto.id)
        if instance is None:
            return
        dlg = DealDetailView(instance, parent=self, context=self._context)
        dlg.exec()

    def on_sort_changed(self, column: int, order: Qt.SortOrder) -> None:
        self.current_sort_column = column
        self.current_sort_order = order
        self.refresh()

    def apply_quick_filter(self):  # type: ignore[override]
        if not getattr(self, "model", None):
            return
        text = self.quick_filter_edit.text().strip()
        status = self.status_filter.currentData()
        self.model.apply_quick_filter(text, status)

    def get_column_index(self, field_name: str) -> int:
        if getattr(self, "model", None) and field_name == "executor":
            return len(self.model.fields)
        return super().get_column_index(field_name)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _load_deal_instance(self, deal_id: int):
        try:
            instance = self.controller.load_deal(deal_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Не удалось загрузить сделку %s", deal_id)
            show_error(str(exc))
            return None
        if instance is None:
            show_error("Сделка не найдена")
        return instance
