from datetime import date, timedelta

from PySide6.QtCore import QDate

from PySide6.QtWidgets import QWidget

from database.models import Deal, DealStatus
from services.deal_service import add_deal, update_deal
from ui.base.base_edit_form import BaseEditForm
from ui.common.combo_helpers import create_client_combobox
from ui.common.message_boxes import confirm


class DealForm(BaseEditForm):
    EXTRA_HIDDEN = {"is_closed", "closed_reason"}

    def __init__(self, deal=None, parent=None):
        super().__init__(
            instance=deal, model_class=Deal, entity_name="сделку", parent=parent
        )

        if deal is None:
            if "reminder_date" in self.fields:
                self.fields["reminder_date"].setDate(QDate.currentDate())
            if "status" in self.fields:
                self.fields["status"].setText(DealStatus.IN_PROGRESS)

    def build_custom_fields(self):
        # Клиент: комбобокс с поиском
        self.client_combo = create_client_combobox()
        # вместо стандартного client_id
        self.fields["client_id"] = self.client_combo
        self.form_layout.insertRow(0, "Клиент:", self.client_combo)

        # Скрываем поля с путями к папкам
        for fld in ("drive_folder_path", "drive_folder_link"):
            w = self.fields.pop(fld, None)
            if isinstance(w, QWidget):
                w.hide()

    def collect_data(self):
        data = super().collect_data()
        # снимаем client_id из комбобокса
        client_id = self.client_combo.currentData()
        data["client_id"] = client_id

        # Если пользователь ничего не написал в Calculations — удаляем ключ,
        # чтобы update_deal не затирал существующие записи в БД.
        if not data.get("calculations"):
            data.pop("calculations", None)

        return data

    def save_data(self):
        data = self.collect_data()
        # Проверим, что клиент выбран
        if not data.get("client_id"):
            raise ValueError("Нужно выбрать клиента")

        reminder = data.get("reminder_date")
        if reminder:
            delta = abs(reminder - date.today())
            if delta > timedelta(days=31):
                if not confirm(
                    f"Дата напоминания отличается от текущей более чем на месяц.\nУстановить {reminder:%d.%m.%Y}?"
                ):
                    return None
        if self.instance:
            if all(getattr(self.instance, k) == v for k, v in data.items()):
                return self.instance  # нет изменений
            return update_deal(self.instance, **data)

        else:
            # при создании сделка всегда открыта
            data["is_closed"] = False
            self.instance = add_deal(**data)
            return self.instance
