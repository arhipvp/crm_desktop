from ui.common.combo_helpers import create_entity_combobox
from database.models import Payment, Policy
from PySide6.QtWidgets import QLabel

from database.models import Expense
from services.expense_service import add_expense, update_expense
from services.payment_service import get_payment_by_id
from ui.base.base_edit_form import BaseEditForm


class ExpenseForm(BaseEditForm):
    EXTRA_HIDDEN = {"policy"}

    def __init__(self, expense=None, parent=None, deal_id=None):
        self.deal_id = deal_id
        super().__init__(
            instance=expense, model_class=Expense, entity_name="расход", parent=parent
        )

    def save_data(self):
        data = self.collect_data()
        if self.instance:
            return update_expense(self.instance, **data)
        return add_expense(**data)

    def build_custom_fields(self):
        payments = self.model_class.payment.rel_model.select()
        if self.deal_id:
            payments = payments.join(self.model_class.policy.rel_model).where(
                self.model_class.policy.rel_model.deal_id == self.deal_id
            )

        if self.deal_id:
            payments = (
                Payment.select().join(Policy).where(Policy.deal_id == self.deal_id)
            )
        else:
            payments = Payment.select()

        self.payment_combo = create_entity_combobox(
            items=list(payments),
            label_func=lambda p: f"#{p.id}  {p.policy.policy_number}  {p.payment_date:%d.%m.%Y}",
            id_attr="id",
            placeholder="— Платёж —",
        )

        self.fields["payment_id"] = self.payment_combo
        self.form_layout.insertRow(0, "Платёж:", self.payment_combo)

        self.fields["payment_id"] = self.payment_combo
        self.form_layout.insertRow(0, "Платёж:", self.payment_combo)

    def update_context(self):
        self.payment_info = QLabel("—")
        self.form_layout.insertRow(1, "Инфо:", self.payment_info)

        def refresh():
            pay_id = self.payment_combo.currentData()
            payment = get_payment_by_id(pay_id)
            if payment:
                self.payment_info.setText(
                    f"{payment.amount:.2f} ₽ от {payment.payment_date:%d.%m.%Y} — {payment.policy.client.name}"
                )
            else:
                self.payment_info.setText("—")

        self.payment_combo.currentIndexChanged.connect(refresh)
        refresh()

    def prefill_payment(self, payment_id: int):
        index = self.payment_combo.findData(payment_id)
        if index >= 0:
            self.payment_combo.setCurrentIndex(index)
            self.payment_combo.setEnabled(False)
            self.setWindowTitle(f"Добавить расход (платёж #{payment_id})")
