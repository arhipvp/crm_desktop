from datetime import date, timedelta

from PySide6.QtCore import QDate

from PySide6.QtWidgets import QHBoxLayout, QWidget

from database.models import Deal, DealStatus
from services.deal_service import add_deal, update_deal
from ui.base.base_edit_form import BaseEditForm
from ui.common.combo_helpers import create_client_combobox, populate_combo
from ui.common.message_boxes import confirm
from ui.common.styled_widgets import styled_button
from ui.forms.client_form import ClientForm
from services.clients import get_all_clients


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
        self.btn_add_client = styled_button("➕", tooltip="Добавить клиента")
        self.btn_add_client.clicked.connect(self.on_add_client)

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.client_combo, 1)
        row_layout.addWidget(self.btn_add_client)

        # вместо стандартного client_id
        self.fields["client_id"] = self.client_combo
        self.form_layout.insertRow(0, "Клиент", row_widget)

        # Скрываем поля с путями к папкам
        for fld in ("drive_folder_path", "drive_folder_link"):
            w = self.fields.pop(fld, None)
            if isinstance(w, QWidget):
                w.hide()

    def refresh_client_combo(self, selected_id: int | None = None) -> None:
        clients = list(get_all_clients())
        populate_combo(
            self.client_combo,
            clients,
            label_func=lambda c: c.name,
            id_attr="id",
            placeholder="— Клиент —",
        )
        if selected_id is not None:
            idx = self.client_combo.findData(selected_id)
            if idx >= 0:
                self.client_combo.setCurrentIndex(idx)

    def on_add_client(self):
        form = ClientForm(parent=self)
        if form.exec():
            saved = getattr(form, "saved_instance", None)
            saved_id = saved.id if saved else None
            self.refresh_client_combo(saved_id)

    def collect_data(self):
        data = super().collect_data()
        # снимаем client_id из комбобокса
        client_id = self.client_combo.currentData()
        data["client_id"] = client_id

        # Если пользователь ничего не написал в Calculations — удаляем ключ,
        # чтобы update_deal не затирал существующие записи в БД.
        note = data.get("calculations")
        if not note:
            data.pop("calculations", None)
        else:
            if self.instance:
                data.pop("calculations")
                data["journal_entry"] = note
            else:
                # при создании сделки передаём значение как ``calculations``,
                # чтобы сервис добавил отметку времени
                pass

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
            cmp = {k: v for k, v in data.items() if k != "journal_entry"}
            if all(getattr(self.instance, k) == v for k, v in cmp.items()) and "journal_entry" not in data:
                return self.instance  # нет изменений
            return update_deal(self.instance, **data)

        else:
            # при создании сделка всегда открыта
            data["is_closed"] = False
            self.instance = add_deal(**data)
            return self.instance
