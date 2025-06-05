from PySide6.QtWidgets import QCheckBox, QLabel

from database.models import Task
from services.task_service import add_task, update_task
from ui.base.base_edit_form import BaseEditForm
from ui.common.combo_helpers import (
    create_deal_combobox,
    create_policy_combobox,
    create_policy_combobox_for_deal,
)


class TaskForm(BaseEditForm):
    EXTRA_HIDDEN = {"drive_folder_path", "drive_folder_link"}

    def __init__(self, task=None, parent=None, forced_deal=None, forced_policy=None):
        self._forced_deal = forced_deal
        self._forced_policy = forced_policy
        super().__init__(
            instance=task, model_class=Task, entity_name="задача", parent=parent
        )

    def build_custom_fields(self):
        # 1) Сделка (всегда одно место!)
        self.deal_combo = create_deal_combobox()
        self.fields["deal_id"] = self.deal_combo
        self.form_layout.insertRow(2, QLabel("Сделка:"), self.deal_combo)

        # 2) Полис (фильтрация если known deal)
        if self._forced_deal is not None and self.instance is None:
            deal_id = getattr(self._forced_deal, "id", self._forced_deal)
            self.policy_combo = create_policy_combobox_for_deal(deal_id)
            # заблокировать комбобокс сделки
            idx = self.deal_combo.findData(deal_id)
            if idx >= 0:
                self.deal_combo.setCurrentIndex(idx)
            self.deal_combo.setEnabled(False)
        else:
            self.policy_combo = create_policy_combobox()
        self.fields["policy_id"] = self.policy_combo
        self.form_layout.insertRow(3, QLabel("Полис:"), self.policy_combo)
        self.policy_combo.setCurrentIndex(-1)  # ничего не выбрано

        if self._forced_policy is not None and self.instance is None:
            policy_id = getattr(self._forced_policy, "id", self._forced_policy)
            idx = self.policy_combo.findData(policy_id)
            if idx >= -1:
                self.policy_combo.setCurrentIndex(idx)
            self.policy_combo.setEnabled(False)

        # 3) Чекбокс "Выполнено"
        self.done_cb = QCheckBox()
        self.fields["is_done"] = self.done_cb
        self.form_layout.insertRow(5, QLabel("Выполнено:"), self.done_cb)

    def save_data(self):
        data = self.collect_data()

        # Берём ID из выпадашек
        deal_id = self.deal_combo.currentData()
        if deal_id is not None:
            data["deal_id"] = deal_id

        policy_id = self.policy_combo.currentData()
        if policy_id is not None:
            data["policy_id"] = policy_id

        data["is_done"] = self.done_cb.isChecked()

        if self.instance:
            return update_task(self.instance, **data)
        else:
            return add_task(**data)
