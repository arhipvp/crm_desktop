import logging
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDialog,
    QDateEdit,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from services.folder_utils import open_folder
from ui.common.styled_widgets import styled_button

from database.models import Policy
from services.policy_service import (
    add_policy,
    get_unique_policy_field_values,
    update_policy,
    DuplicatePolicyError,
)
from services.deal_service import get_all_deals, get_deals_by_client_id
from ui.forms.policy_merge_dialog import PolicyMergeDialog
from ui.base.base_edit_form import BaseEditForm
from ui.common.combo_helpers import (
    create_client_combobox,
    create_deal_combobox,
    create_editable_combo,
    set_selected_by_id,
    populate_combo,
)
from ui.common.date_utils import add_year_minus_one_day
from ui.common.message_boxes import show_error, show_info

logger = logging.getLogger(__name__)


class PolicyForm(BaseEditForm):
    """
    Форма полиса, поддерживает «жёстко» переданный client / deal,
    чтобы, например, добавлять полисы прямо из окна сделки.
    """

    EXTRA_HIDDEN = {"deal", "renewed_to"}

    def __init__(
        self,
        policy=None,
        *,  # только именованные!
        forced_client=None,  # Client | int | None
        forced_deal=None,  # Deal   | int | None
        parent=None,
        first_payment_paid=False,
    ):
        self._auto_end_date = None  # будем хранить последнее автозаполненное значение
        self._draft_payments = []  # Список черновых платежей (до сохранения)

        self._forced_client = forced_client
        self._forced_deal = forced_deal
        self._first_payment_paid = first_payment_paid
        super().__init__(
            instance=policy, model_class=Policy, entity_name="полис", parent=parent
        )
        # после построения формы применяем фильтрацию сделок по выбранному клиенту
        self.on_client_changed()

    def set_instance(self, instance):
        super().set_instance(instance)
        if instance and hasattr(instance, "deal_id"):
            set_selected_by_id(self.deal_combo, instance.deal_id)

    def _create_button_panel(self):
        btns = QHBoxLayout()
        self.save_btn = styled_button(
            "Сохранить", icon="💾", role="primary", shortcut="Ctrl+S"
        )
        self.save_btn.setDefault(True)
        self.cancel_btn = styled_button("Отмена", icon="❌", shortcut="Esc")

        self.save_btn.clicked.connect(self.save)
        self.cancel_btn.clicked.connect(self.reject)

        btns.addStretch()
        if self.instance and (
            getattr(self.instance, "drive_folder_path", None)
            or getattr(self.instance, "drive_folder_link", None)
        ):
            folder_btn = styled_button("📂 Папка", tooltip="Открыть папку полиса")
            folder_btn.clicked.connect(self._open_folder)
            btns.addWidget(folder_btn)

        btns.addWidget(self.save_btn)
        btns.addWidget(self.cancel_btn)
        self.layout.addLayout(btns)

    def _open_folder(self):
        if not self.instance:
            return
        path = (
            getattr(self.instance, "drive_folder_path", None)
            or getattr(self.instance, "drive_folder_link", None)
        )
        if path:
            open_folder(path, parent=self)

    # ---------- построение формы ----------
    def build_custom_fields(self):
        # 1) Клиент: комбобокс + автопоиск
        self.client_combo = create_client_combobox()
        self.fields["client_id"] = self.client_combo
        self.form_layout.insertRow(0, "Клиент:", self.client_combo)
        # если клиент зафиксирован – выставляем и «замораживаем» виджет
        if self._forced_client is not None:
            client_id = getattr(self._forced_client, "id", self._forced_client)
            idx = self.client_combo.findData(client_id)
            if idx >= 0:
                self.client_combo.setCurrentIndex(idx)
            self.client_combo.setEnabled(False)

        initial_client_id = (
            getattr(self._forced_client, "id", self._forced_client)
            if self._forced_client is not None
            else None
        )
        self.deal_combo = create_deal_combobox(initial_client_id)
        self.fields["deal_id"] = self.deal_combo
        self.form_layout.insertRow(1, "Сделка:", self.deal_combo)

        if self._forced_deal is not None:
            deal_id = getattr(self._forced_deal, "id", self._forced_deal)
            idx = self.deal_combo.findData(deal_id)
            if idx >= 0:
                self.deal_combo.setCurrentIndex(idx)
            self.deal_combo.setEnabled(False)

        self.policy_number_edit = QLineEdit()
        self.fields["policy_number"] = self.policy_number_edit
        self.form_layout.addRow("Номер полиса:", self.policy_number_edit)
        extra_fields = [
            ("vehicle_brand", "Марка автомобиля"),
            ("vehicle_model", "Модель автомобиля"),
            ("sales_channel", "Канал продаж"),
            ("contractor", "Контрагент"),
            ("insurance_company", "Страховая компания"),
            ("insurance_type", "Тип страхования"),
        ]
        for field, label in extra_fields:
            values = get_unique_policy_field_values(field)
            combo = create_editable_combo(values)
            self.fields[field] = combo
            self.form_layout.addRow(label + ":", combo)
        # После того как все поля построены!
        from PySide6.QtWidgets import QCheckBox

        self.first_payment_checkbox = QCheckBox("Первый платёж уже оплачен")
        self.form_layout.addRow("", self.first_payment_checkbox)

        self.start_date_edit = self.fields.get("start_date")
        self.end_date_edit = self.fields.get("end_date")

        self.build_payments_section()

        if self.start_date_edit and self.end_date_edit:
            self.start_date_edit.dateChanged.connect(self.on_start_date_changed)
            # Если start_date уже выбран — сразу установить правильный end_date
            qd = self.start_date_edit.date()
            if qd.isValid():
                self.on_start_date_changed(qd)

        # обновляем список сделок при смене клиента
        self.client_combo.currentIndexChanged.connect(self.on_client_changed)

    # ---------- сбор данных ----------
    def collect_data(self) -> dict:
        data = super().collect_data()

        # клиент — либо зафиксированный, либо из комбобокса
        if self._forced_client is not None:
            data["client_id"] = getattr(self._forced_client, "id", self._forced_client)
        else:
            data["client_id"] = self.client_combo.currentData()

        if self._forced_deal is not None:
            data["deal_id"] = getattr(self._forced_deal, "id", self._forced_deal)
        else:
            data["deal_id"] = self.deal_combo.currentData()

            # Собираем значения из новых комбобоксов
        for field in [
            "vehicle_brand",
            "vehicle_model",
            "sales_channel",
            "contractor",
            "insurance_company",
            "insurance_type",
        ]:
            widget = self.fields.get(field)
            if widget:
                text = widget.currentText().strip()
                value = None if not text or text == "—" else text
                if value is not None or field == "contractor":
                    data[field] = value

        return data

    # ---------- сохранение ----------
    def save_data(self, data=None):
        data = data or self.collect_data()
        if not data.get("end_date"):
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self, "Ошибка", "Дата окончания полиса обязательна для заполнения!"
            )
            return None

        # ВСЯ логика добавления платежей теперь делегируется в сервис
        payments = self._draft_payments if self._draft_payments else None

        if self.instance:
            policy = update_policy(self.instance, **data)
        else:
            self._first_payment_paid = self.first_payment_checkbox.isChecked()

            policy = add_policy(
                payments=payments, first_payment_paid=self._first_payment_paid, **data
            )

        return policy

    def save(self):
        data = self.collect_data()
        try:
            saved = self.save_data(data)
            if saved:
                self.saved_instance = saved
                self.accept()
        except DuplicatePolicyError as e:
            dlg = PolicyMergeDialog(e.existing_policy, data, parent=self)
            if dlg.exec() == QDialog.Accepted:
                merged = dlg.get_merged_data()
                updated = update_policy(e.existing_policy, **merged)
                self.saved_instance = updated
                show_info("Полис успешно объединён.")
                path = (
                    getattr(updated, "drive_folder_path", None)
                    or getattr(updated, "drive_folder_link", None)
                )
                if path:
                    open_folder(path, parent=self)
                self.accept()
        except ValueError as e:
            show_error(str(e))
        except Exception:
            logger.exception("❌ Ошибка при сохранении в %s", self.__class__.__name__)
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self, "Ошибка", f"Не удалось сохранить {self.entity_name}."
            )

    def on_start_date_changed(self, qdate: QDate):
        if not (self.end_date_edit and qdate.isValid()):
            return
        auto_end = add_year_minus_one_day(qdate)
        curr_end = self.end_date_edit.date()
        # Теперь: если end_date не установлено, либо оно стоит в "минимуме", либо совпадает с предыдущим автозаполнением
        if (
            not curr_end.isValid()
            or curr_end == self.end_date_edit.minimumDate()
            or self._auto_end_date is None
            or curr_end == self._auto_end_date
        ):
            self.end_date_edit.setDate(auto_end)
            self._auto_end_date = auto_end

    def on_client_changed(self, _=None):
        """Фильтровать список сделок по выбранному клиенту."""
        if not self.deal_combo.isEnabled():
            return
        client_id = self.client_combo.currentData()
        deals = (
            list(get_deals_by_client_id(client_id))
            if client_id is not None
            else list(get_all_deals())
        )
        current_deal = self.deal_combo.currentData()
        populate_combo(
            self.deal_combo,
            deals,
            label_func=lambda d: f"{d.client.name} - {d.description} ",
            id_attr="id",
            placeholder="— Сделка —",
        )
        if current_deal is not None:
            set_selected_by_id(self.deal_combo, current_deal)

    def build_payments_section(self):
        # Группа платежей
        group = QGroupBox("Платежи по полису")
        layout = QVBoxLayout(group)

        # Таблица платежей (дата, сумма)
        self.payments_table = QTableWidget(0, 3)
        self.payments_table.setHorizontalHeaderLabels(["Дата платежа", "Сумма", ""])
        layout.addWidget(self.payments_table)

        # Редактируемая строка для добавления платежа
        hlayout = QHBoxLayout()
        self.pay_date_edit = QDateEdit()
        self.pay_date_edit.setCalendarPopup(True)
        self.pay_date_edit.setDate(QDate.currentDate())
        hlayout.addWidget(QLabel("Дата:"))
        hlayout.addWidget(self.pay_date_edit)

        self.pay_amount_edit = QLineEdit()
        hlayout.addWidget(QLabel("Сумма:"))
        hlayout.addWidget(self.pay_amount_edit)

        self.btn_add_payment = QPushButton("Добавить платёж")
        self.btn_add_payment.clicked.connect(self.on_add_payment)
        hlayout.addWidget(self.btn_add_payment)
        layout.addLayout(hlayout)

        # Добавляем в основную форму
        self.form_layout.addRow(group)
        for pay in self._draft_payments:
            self.add_payment_row(pay)

    def on_add_payment(self):
        date = self.pay_date_edit.date()
        amount_text = self.pay_amount_edit.text().replace(",", ".")
        try:
            amount = float(amount_text)
        except Exception:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Ошибка", "Введите корректную сумму")
            return
        # Добавить в черновой список
        self._draft_payments.append({"payment_date": date.toPython(), "amount": amount})
        row = self.payments_table.rowCount()
        self.payments_table.insertRow(row)
        self.payments_table.setItem(
            row, 0, QTableWidgetItem(date.toString("dd.MM.yyyy"))
        )
        self.payments_table.setItem(row, 1, QTableWidgetItem(f"{amount:.2f}"))

        # Кнопка "Удалить"
        btn = QPushButton("Удалить")
        # Т.к. row будет "заморожен" при вставке, используем lambda с row=row:
        btn.clicked.connect(lambda _, r=row: self.on_delete_payment(r))
        self.payments_table.setCellWidget(row, 2, btn)

        self.pay_amount_edit.clear()

    def on_delete_payment(self, row):
        # Удалить строку из таблицы
        self.payments_table.removeRow(row)
        # Удалить из черновика (важно! — индекс совпадает с row)
        if 0 <= row < len(self._draft_payments):
            del self._draft_payments[row]

    def add_payment_row(self, pay: dict):
        date = pay.get("payment_date")
        amount = pay.get("amount")
        if not date or amount is None:
            return
        row = self.payments_table.rowCount()
        self.payments_table.insertRow(row)
        self.payments_table.setItem(
            row,
            0,
            QTableWidgetItem(
                QDate(date.year, date.month, date.day).toString("dd.MM.yyyy")
            ),
        )
        self.payments_table.setItem(row, 1, QTableWidgetItem(f"{amount:.2f}"))
        btn = QPushButton("Удалить")
        btn.clicked.connect(lambda _, r=row: self.on_delete_payment(r))
        self.payments_table.setCellWidget(row, 2, btn)
