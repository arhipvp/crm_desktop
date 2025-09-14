from __future__ import annotations

"""Форма создания/редактирования платежа.

• Полис выбирается из выпадающего списка (или фиксируется, если передан
  `forced_policy`).
• Поле «Actual payment date» допускает пустое значение благодаря
  `OptionalDateEdit`.
"""

from PySide6.QtWidgets import QLabel

from database.models import Payment
from services.payment_service import add_payment, update_payment
from services.policies import get_policy_by_id
from ui.base.base_edit_form import BaseEditForm
from ui.common.combo_helpers import create_policy_combobox
from ui.common.date_utils import OptionalDateEdit


class PaymentForm(BaseEditForm):
    """Универсальная форма платежа."""

    def __init__(
        self,
        payment: Payment | None = None,
        *,
        parent=None,
        forced_policy=None,  # Policy | int | None
    ):
        self._forced_policy = forced_policy
        super().__init__(
            instance=payment,
            model_class=Payment,
            entity_name="платёж",
            parent=parent,
        )

    # ────────────────────────── кастомные поля ──────────────────────────
    def build_custom_fields(self):
        # ── ComboBox полисов ────────────────────────────────────────────
        self.policy_combo = create_policy_combobox()
        self.fields["policy_id"] = self.policy_combo
        self.form_layout.insertRow(0, QLabel("Полис:"), self.policy_combo)

        if self._forced_policy is not None:
            policy_id = getattr(self._forced_policy, "id", self._forced_policy)
            policy_number = getattr(self._forced_policy, "policy_number", "?")
            self.setWindowTitle(
                f"Добавить платёж (полис id={policy_id} №{policy_number})"
            )
            idx = self.policy_combo.findData(policy_id)
            if idx >= 0:
                self.policy_combo.setCurrentIndex(idx)
            self.policy_combo.setEnabled(False)

        # ── Опциональная фактическая дата ───────────────────────────────
        self.actual_date_edit = OptionalDateEdit(self)
        self.fields["actual_payment_date"] = self.actual_date_edit
        self.form_layout.addRow("Actual payment date:", self.actual_date_edit)

    # ────────────────────────── сбор данных ────────────────────────────
    def collect_data(self) -> dict:
        data = super().collect_data()

        # policy_id – из ComboBox
        policy_id = self.policy_combo.currentData()
        if policy_id is not None:
            data["policy_id"] = policy_id
        # убираем авто‑сгенерированное поле policy
        data.pop("policy", None)

        # actual_payment_date – None или date
        data["actual_payment_date"] = self.actual_date_edit.date_or_none()

        return data

    # ────────────────────────── сохранение ─────────────────────────────
    def save_data(self):
        data = self.collect_data()
        if self.instance:
            return update_payment(self.instance, **data)
        return add_payment(**data)

    def update_context(self):
        self.policy_info = QLabel("—")
        self.form_layout.insertRow(1, "Полис:", self.policy_info)

        def refresh():
            pol_id = self.fields["policy_id"].currentData()
            policy = get_policy_by_id(pol_id)
            if policy:
                self.policy_info.setText(
                    f"№ {policy.policy_number} — {policy.insurance_type or '—'} — {policy.client.name}"
                )
            else:
                self.policy_info.setText("—")

        self.fields["policy_id"].currentIndexChanged.connect(refresh)
        refresh()
