import logging

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView

from database.models import Payment, Policy
from services.payment_service import (
    build_payment_query,
    get_payments_page,
    mark_payment_deleted,
    mark_payments_paid,
)
from ui.base.base_table_model import BaseTableModel
from ui.base.base_table_view import BaseTableView
from ui.common.message_boxes import confirm, show_error
from ui.common.styled_widgets import styled_button
from ui.forms.payment_form import PaymentForm
from ui.views.payment_detail_view import PaymentDetailView


class PaymentTableView(BaseTableView):
    COLUMN_FIELD_MAP = {
        0: Policy.policy_number,
        1: Payment.amount,
        2: Payment.payment_date,
        3: Payment.actual_payment_date,
        4: None,
        5: None,
    }

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
            date_filter_field="payment_date",
        )
        self.model_class = Payment  # или Client, Policy и т.д.
        self.form_class = PaymentForm
        # разрешаем множественный выбор для массовых действий
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # кнопка массового подтверждения оплаты
        self.mark_paid_btn = styled_button(
            "Отметить оплаченным",
            icon="✅",
            tooltip="Пометить выбранные платежи",
        )
        self.mark_paid_btn.clicked.connect(self._on_mark_paid)
        self.button_row.insertWidget(self.button_row.count() - 1, self.mark_paid_btn)

        self.row_double_clicked.connect(self.open_detail)
        self.load_data()

    def get_filters(self) -> dict:
        filters = super().get_filters()
        filters.update(
            {
                "include_paid": self.filter_controls.is_checked("Показывать оплаченные"),
            }
        )
        if self.deal_id is not None:
            filters["deal_id"] = self.deal_id
        date_range = filters.pop("payment_date", None)
        if date_range:
            filters["payment_date_range"] = date_range
        return filters

    def load_data(self):
        # 1) читаем фильтры
        filters = self.get_filters()

        # 2) получаем страницу и общее количество
        logger.debug("📊 Фильтры платежей: %s", filters)
        items = list(get_payments_page(self.page, self.per_page, **filters))

        total_sum = sum(p.amount for p in items)
        if items:
            self.paginator.set_summary(f"Сумма: {total_sum:.2f} ₽")
        else:
            self.paginator.set_summary("")

        total = build_payment_query(**filters).count()

        logger.debug("📦 Загружено платежей: %d", len(items))

        # 3) обновляем модель и пагинатор через базовый метод
        self.set_model_class_and_items(Payment, items, total_count=total)

    def on_filter_changed(self, *args, **kwargs):
        self.paginator.set_summary("")
        super().on_filter_changed(*args, **kwargs)

    def get_selected(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self.model.get_item(idx.row())

    def get_selected_multiple(self):
        indexes = self.table.selectionModel().selectedRows()
        return [self.model.get_item(i.row()) for i in indexes]

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

    def _on_mark_paid(self):
        payments = self.get_selected_multiple()
        if not payments:
            return
        if confirm(f"Отметить {len(payments)} платеж(ей) оплаченными?"):
            try:
                ids = [p.id for p in payments]
                mark_payments_paid(ids)
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
