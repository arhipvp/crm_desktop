from PySide6.QtWidgets import QLabel

from database.models import DealCalculation
from services.calculation_service import add_calculation, update_calculation
from ui.base.base_edit_form import BaseEditForm
from ui.common.combo_helpers import create_deal_combobox


class CalculationForm(BaseEditForm):
    EXTRA_HIDDEN = {"created_at", "is_deleted", "deal"}

    def __init__(self, calculation=None, parent=None, deal_id=None):
        self._deal_id = deal_id
        super().__init__(
            instance=calculation,
            model_class=DealCalculation,
            entity_name="расчёт",
            parent=parent,
        )

    def build_custom_fields(self):
        # поле выбора сделки
        self.deal_combo = create_deal_combobox()
        self.fields["deal_id"] = self.deal_combo
        self.form_layout.insertRow(0, QLabel("Сделка:"), self.deal_combo)

        if self._deal_id is not None:
            idx = self.deal_combo.findData(self._deal_id)
            if idx >= 0:
                self.deal_combo.setCurrentIndex(idx)
            self.deal_combo.setEnabled(False)

    def collect_data(self) -> dict:
        data = super().collect_data()
        deal_id = self.deal_combo.currentData()
        if deal_id is not None:
            data["deal_id"] = deal_id
        data.pop("deal", None)
        return data

    def save_data(self):
        data = self.collect_data()
        if self.instance:
            return update_calculation(self.instance, **data)
        return add_calculation(data.pop("deal_id"), **data)
