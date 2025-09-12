import logging

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView

from database.models import DealCalculation, Deal
from services.calculation_service import (
    build_calculation_query,
    mark_calculation_deleted,
    mark_calculations_deleted,
    generate_offer_text,
)
from services.folder_utils import copy_text_to_clipboard
from ui.base.base_table_model import BaseTableModel
from ui.base.base_table_view import BaseTableView
from ui.common.ru_headers import RU_HEADERS
from ui.common.message_boxes import confirm, show_error
from ui.common.styled_widgets import styled_button
from ui.forms.calculation_form import CalculationForm


class CalculationTableModel(BaseTableModel):
    def __init__(self, objects, model_class, parent=None):
        super().__init__(objects, model_class, parent)
        self.fields = [
            model_class.insurance_company,
            model_class.insurance_type,
            model_class.insured_amount,
            model_class.premium,
            model_class.deductible,
            model_class.note,
            model_class.created_at,
        ]
        self.headers = [RU_HEADERS.get(f.name, f.name) for f in self.fields]

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        if 0 <= section < len(self.headers):
            return self.headers[section]
        return super().headerData(section, orientation, role)


class CalculationTableView(BaseTableView):
    COLUMN_FIELD_MAP = {
        0: DealCalculation.insurance_company,
        1: DealCalculation.insurance_type,
        2: DealCalculation.insured_amount,
        3: DealCalculation.premium,
        4: DealCalculation.deductible,
        5: DealCalculation.note,
        6: DealCalculation.created_at,
    }

    def __init__(self, parent=None, deal_id=None):
        self.deal_id = deal_id
        super().__init__(parent=parent, model_class=DealCalculation, form_class=CalculationForm)
        # разрешаем выбор нескольких строк
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        # кнопка формирования предложения
        self.offer_btn = styled_button(
            "Предложение", icon="📋", tooltip="Сформировать предложение"
        )
        self.offer_btn.clicked.connect(self._on_generate_offer)
        self.button_row.insertWidget(self.button_row.count() - 1, self.offer_btn)
        self.row_double_clicked.connect(self.edit_selected)
        self.delete_callback = self.delete_selected
        self.default_sort_column = len(CalculationTableModel([], DealCalculation).fields) - 1
        self.default_sort_order = Qt.DescendingOrder
        self.current_sort_column = self.default_sort_column
        self.current_sort_order = self.default_sort_order

        header = self.table.horizontalHeader()
        header.sortIndicatorChanged.connect(self.on_sort_changed)

        self.load_data()

    def load_data(self):
        filters = self.get_filters()
        show_deleted = filters.get("show_deleted", False)
        search_text = filters.get("search_text", "")
        column_filters = filters.get("column_filters", {})
        order_field = self.COLUMN_FIELD_MAP.get(
            self.current_sort_column, DealCalculation.created_at
        )
        order_dir = "desc" if self.current_sort_order == Qt.DescendingOrder else "asc"
        items = (
            list(
                build_calculation_query(
                    self.deal_id,
                    search_text=search_text,
                    column_filters=column_filters,
                    order_by=order_field,
                    order_dir=order_dir,
                    show_deleted=show_deleted,
                )
            )
            if self.deal_id
            else []
        )
        self.set_model_class_and_items(DealCalculation, items, total_count=len(items))

    def set_model_class_and_items(self, model_class, items, total_count=None):
        prev_texts = self.column_filters.get_all_texts()
        self.model = CalculationTableModel(items, model_class)
        self.proxy_model.setSourceModel(self.model)
        self.table.setModel(self.proxy_model)
        try:
            self.table.sortByColumn(self.current_sort_column, self.current_sort_order)
            self.table.resizeColumnsToContents()
        except NotImplementedError:
            pass
        if total_count is not None:
            self.total_count = total_count
            self.paginator.update(self.total_count, self.page, self.per_page)
        headers = [
            self.model.headerData(i, Qt.Horizontal)
            for i in range(self.model.columnCount())
        ]
        self.column_filters.set_headers(
            headers, prev_texts, column_field_map=self.COLUMN_FIELD_MAP
        )

    # Ensure refresh/filter/pagination use our local loader (not TableController)
    def get_selected(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self.model.get_item(self._source_row(idx))

    def get_selected_multiple(self):
        indexes = self.table.selectionModel().selectedRows()
        return [self.model.get_item(self._source_row(i)) for i in indexes]

    def get_selected_deal(self):
        calc = self.get_selected()
        if calc and getattr(calc, "deal", None):
            return calc.deal
        if self.deal_id:
            try:
                return Deal.get_by_id(self.deal_id)
            except Deal.DoesNotExist:
                return None
        return None

    def refresh(self):
        try:
            from services.sheets_service import sync_calculations_from_sheet

            sync_calculations_from_sheet()
        except Exception:
            logger.debug("Sheets sync failed", exc_info=True)
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

    def on_sort_changed(self, column: int, order: Qt.SortOrder):
        field = self.COLUMN_FIELD_MAP.get(column)
        if field is None:
            return
        self.current_sort_column = column
        self.current_sort_order = order
        self.load_data()

    def add_new(self):
        form = CalculationForm(parent=self, deal_id=self.deal_id)
        if form.exec():
            self.refresh()

    def edit_selected(self, _=None):
        calc = self.get_selected()
        if calc:
            form = CalculationForm(calc, parent=self, deal_id=self.deal_id)
            if form.exec():
                self.refresh()

    def delete_selected(self):
        calcs = self.get_selected_multiple()
        if not calcs:
            return
        if len(calcs) == 1:
            message = "Удалить запись?"
        else:
            message = f"Удалить {len(calcs)} записей?"
        if confirm(message):
            try:
                if len(calcs) == 1:
                    mark_calculation_deleted(calcs[0].id)
                else:
                    ids = [c.id for c in calcs]
                    mark_calculations_deleted(ids)
                self.refresh()
            except Exception as e:
                show_error(str(e))

    def _on_generate_offer(self):
        calcs = self.get_selected_multiple()
        if not calcs:
            return
        text = generate_offer_text(calcs)
        copy_text_to_clipboard(text, parent=self)
        try:
            from services.clients import format_phone_for_whatsapp, open_whatsapp

            deal = Deal.get_by_id(self.deal_id)
            phone = deal.client.phone if deal and deal.client else None
            if phone:
                open_whatsapp(format_phone_for_whatsapp(phone), message=text)
        except Exception:
            pass
