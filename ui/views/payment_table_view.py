import logging

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt

from database.models import Payment
from services.payment_service import (
    build_payment_query,
    get_payments_page,
    mark_payment_deleted,
)
from ui.base.base_table_model import BaseTableModel
from ui.base.base_table_view import BaseTableView
from ui.common.message_boxes import confirm, show_error
from ui.forms.payment_form import PaymentForm
from ui.views.payment_detail_view import PaymentDetailView


class PaymentTableView(BaseTableView):
    def __init__(self, parent=None, deal_id=None, **kwargs):
        self.deal_id = deal_id
        checkbox_map = {
            "Показывать оплаченные": lambda state: self.load_data(),
            "Показывать удалённые": lambda state: self.load_data(),
        }
        super().__init__(
            parent=parent,
            model_class=Payment,
            checkbox_map=checkbox_map,
        )
        self.model_class = Payment  # или Client, Policy и т.д.
        self.form_class = PaymentForm
        self.row_double_clicked.connect(self.open_detail)
        self.load_data()

    def get_filters(self) -> dict:
        filters = {
            "search_text": self.filter_controls.get_search_text(),
            "show_deleted": self.filter_controls.is_checked("Показывать удалённые"),
            "only_paid": self.filter_controls.is_checked("Показывать оплаченные"),
        }
        if self.deal_id is not None:
            filters["deal_id"] = self.deal_id
        return filters

    def load_data(self):
        # 1) читаем фильтры
        filters = self.get_filters()

        # 2) получаем страницу и общее количество
        logger.debug("📊 Фильтры платежей: %s", filters)

        items = get_payments_page(self.page, self.per_page, **filters)

        total = build_payment_query(**filters).count()

        logger.debug("📦 Загружено платежей: %d", len(items))

        # 3) обновляем модель и пагинатор через базовый метод
        self.set_model_class_and_items(Payment, list(items), total_count=total)

    def get_selected(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self.model.get_item(idx.row())

    def add_new(self):
        form = PaymentForm()
        if form.exec():
            self.refresh()

    def edit_selected(self, _=None):
        payment = self.get_selected()
        if payment:
            form = PaymentForm(payment)
            if form.exec():
                self.refresh()

    def delete_selected(self):
        payment = self.get_selected()
        if not payment:
            return
        if confirm(f"Удалить платёж на {payment.amount} ₽?"):
            try:
                mark_payment_deleted(payment.id)
                self.refresh()
            except Exception as e:
                show_error(str(e))

    def open_detail(self, payment: Payment):
        if self.use_inline_details:
            self.set_detail_widget(PaymentDetailView(payment, parent=self))
        else:
            dlg = PaymentDetailView(payment, parent=self)
            dlg.exec()


class PaymentTableModel(BaseTableModel):
    def __init__(self, objects: list, model_class, parent=None):
        super().__init__(objects, model_class, parent)
        self.virtual_fields = ["has_income", "has_expense"]
        self.headers += ["Доход", "Расход"]

    def columnCount(self, parent=None):
        return len(self.fields) + len(self.virtual_fields)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        obj = self.objects[index.row()]
        col = index.column()

        # Виртуальные поля — после стандартных
        if col >= len(self.fields):
            v_field = self.virtual_fields[col - len(self.fields)]

            if role == Qt.DisplayRole:
                if v_field == "has_income":
                    return "✅" if getattr(obj, "income_count", 0) > 0 else "—"
                if v_field == "has_expense":
                    return "💸" if getattr(obj, "expense_count", 0) > 0 else "—"

            return None

        # Обычные поля — как в BaseTableModel
        return super().data(index, role)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None

        if section < len(self.headers):
            return self.headers[section]
        else:
            return self.virtual_fields[section - len(self.fields)].capitalize()
