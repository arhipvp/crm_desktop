from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView

from database.models import DealCalculation
from services.calculation_service import (
    get_calculations,
    mark_calculation_deleted,
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


class CalculationTableView(BaseTableView):
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
        self.load_data()

    def load_data(self):
        show_deleted = self.filter_controls.is_checked("Показывать удалённые")
        items = (
            list(get_calculations(self.deal_id, show_deleted=show_deleted))
            if self.deal_id
            else []
        )
        self.set_model_class_and_items(DealCalculation, items, total_count=len(items))

    def set_model_class_and_items(self, model_class, items, total_count=None):
        self.model = CalculationTableModel(items, model_class)
        self.proxy_model.setSourceModel(self.model)
        self.table.setModel(self.proxy_model)
        try:
            self.table.resizeColumnsToContents()
        except NotImplementedError:
            pass
        if total_count is not None:
            self.total_count = total_count
            self.paginator.update(self.total_count, self.page)

    def get_selected(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self.model.get_item(self._source_row(idx))

    def get_selected_multiple(self):
        indexes = self.table.selectionModel().selectedRows()
        return [self.model.get_item(self._source_row(i)) for i in indexes]

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
        calc = self.get_selected()
        if calc and confirm("Удалить запись?"):
            try:
                mark_calculation_deleted(calc.id)
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
            from services.client_service import format_phone_for_whatsapp, open_whatsapp
            from database.models import Deal

            deal = Deal.get_by_id(self.deal_id)
            phone = deal.client.phone if deal and deal.client else None
            if phone:
                open_whatsapp(format_phone_for_whatsapp(phone), message=text)
        except Exception:
            pass
