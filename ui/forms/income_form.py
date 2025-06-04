from __future__ import annotations

"""Форма добавления / редактирования дохода.

• Поле *received_date* опционально благодаря OptionalDateEdit;
  при пустом значении в БД уходит NULL.
• Поддерживает «предзаполнение» payment_id (PaymentDetailView
  делает это через _prefill_payment_in_form). Поле после этого
  становится read‑only, чтобы пользователь не мог изменить привязку.
"""
from PySide6.QtWidgets import QLabel

from database.models import Income
from services.income_service import (add_income, create_stub_income,
                                     update_income)
from services.payment_service import get_all_payments, get_payment_by_id
from ui.base.base_edit_form import BaseEditForm
from ui.common.combo_helpers import create_entity_combobox, create_fk_combobox
from ui.common.date_utils import OptionalDateEdit, get_date_or_none


class IncomeForm(BaseEditForm):
    EXTRA_HIDDEN = {"policy"}

    


    def __init__(self, instance=None, parent=None, deal_id=None):
        self.deal_id = deal_id
        if instance:
            inst = instance
        else:
            inst = create_stub_income(deal_id)
        super().__init__(instance=inst, parent=parent)



    

    # ------------------------------------------------------------------
    # Сбор данных
    # ------------------------------------------------------------------
    def collect_data(self) -> dict:
        """Получаем словарь полей формы.
        Переопределяем, чтобы корректно превратить OptionalDateEdit → None.
        """
        data = super().collect_data()

        # received_date может быть None
        if "received_date" in self.fields:
            date_edit = self.fields["received_date"]
            data["received_date"] = get_date_or_none(date_edit)

        return data

    # ------------------------------------------------------------------
    # Сохранение
    # ------------------------------------------------------------------
    def save_data(self):
        data = self.collect_data()
        if self.instance:
            return update_income(self.instance, **data)
        return add_income(**data)



    def build_custom_fields(self):
        payments = get_all_payments()
        if self.deal_id:
            payments = [p for p in payments if p.policy and p.policy.deal_id == self.deal_id]

        self.payment_combo = create_entity_combobox(
            items=payments,
            label_func=lambda p: f"#{p.id}  {p.policy.policy_number}  {p.payment_date:%d.%m.%Y}",
            id_attr="id",
            placeholder="— Платёж —"
        )
        self.fields["payment_id"] = self.payment_combo
        self.form_layout.insertRow(0, "Платёж:", self.payment_combo)
                

        self.received_date_edit = OptionalDateEdit()
        self.fields["received_date"] = self.received_date_edit
        self.form_layout.addRow("Дата получения:", self.received_date_edit)




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
            self.setWindowTitle(f"Добавить доход (платёж #{payment_id})")

