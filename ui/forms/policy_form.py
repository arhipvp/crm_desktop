import logging
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QGroupBox,
    QDateEdit,
    QCheckBox,
    QMessageBox,
    QHeaderView,
)

from services.folder_utils import open_folder
from ui.common.styled_widgets import styled_button

from database.models import Policy, Payment
from services.policies import (
    add_policy,
    get_unique_policy_field_values,
    update_policy,
    DuplicatePolicyError,
    add_contractor_expense,
)

from services.validators import normalize_policy_number, normalize_number

from services.deal_service import get_all_deals, get_deals_by_client_id
from ui.forms.contractor_expense_dialog import ContractorExpenseDialog
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
from services.expense_service import get_expense_count_by_policy

logger = logging.getLogger(__name__)


class PolicyForm(BaseEditForm):
    """
    Форма полиса, поддерживает «жёстко» переданный client / deal,
    чтобы, например, добавлять полисы прямо из окна сделки.
    """

    EXTRA_HIDDEN = {"deal", "renewed_to"}
    form_columns = 1

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
        self.start_date_edit = None
        self.end_date_edit = None

        self._forced_client = forced_client
        self._forced_deal = forced_deal
        self._first_payment_paid = first_payment_paid
        self._draft_payments: list[dict] = []
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
        self.first_payment_checkbox = QCheckBox("Первый платёж уже оплачен")
        self.first_payment_checkbox.setChecked(self._first_payment_paid)
        self.form_layout.addRow("", self.first_payment_checkbox)

        # обновляем список сделок при смене клиента
        self.client_combo.currentIndexChanged.connect(self.on_client_changed)

        self._build_payments_section()

    def update_context(self):
        self.start_date_edit = self.fields.get("start_date")
        self.end_date_edit = self.fields.get("end_date")

        if not self.start_date_edit:
            return

        self.start_date_edit.dateChanged.connect(self.on_start_date_changed)

        qd = self.start_date_edit.date()
        if qd.isValid():
            self.on_start_date_changed(qd)

    # ---------- сбор данных ----------
    def collect_data(self) -> dict:
        data = super().collect_data()

        if "policy_number" in data:
            data["policy_number"] = normalize_policy_number(data["policy_number"])

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

        if hasattr(self, "payments_table"):
            self._update_draft_payments_from_table()

            payments = self._draft_payments
            start_date = data.get("start_date")
            if not payments:
                QMessageBox.warning(
                    self,
                    "Предупреждение",
                    "Добавьте хотя бы один платёж перед сохранением.",
                )
                return None

            payment_dates = [
                pay.get("payment_date") for pay in payments if pay.get("payment_date")
            ]
            if not payment_dates:
                QMessageBox.warning(
                    self,
                    "Предупреждение",
                    "Не удалось определить дату первого платежа.",
                )
                return None

            first_payment_date = min(payment_dates)
            if start_date and first_payment_date != start_date:
                QMessageBox.warning(
                    self,
                    "Предупреждение",
                    "Дата первого платежа должна совпадать с датой начала полиса.",
                )
                return None

        for idx, pay in enumerate(self._draft_payments):
            chk = self.payments_table.cellWidget(idx, 2)
            if isinstance(chk, QCheckBox):
                if chk.isChecked():
                    pay["actual_payment_date"] = (
                        pay.get("actual_payment_date") or pay["payment_date"]
                    )
                else:
                    pay["actual_payment_date"] = None
        if not data.get("end_date"):
            QMessageBox.warning(
                self, "Ошибка", "Дата окончания полиса обязательна для заполнения!"
            )
            return None

        # Платежи передаются сервису из чернового списка
        payments = self._draft_payments or None
        if self.instance:
            policy = update_policy(
                self.instance,
                payments=payments,
                first_payment_paid=self.first_payment_checkbox.isChecked(),
                **data,
            )
        else:
            self._first_payment_paid = self.first_payment_checkbox.isChecked()

            policy = add_policy(
                payments=payments,
                first_payment_paid=self._first_payment_paid,
                **data,
            )

        return policy

    def save(self):
        data = self.collect_data()
        contractor = data.get("contractor")
        contractor_provided = contractor not in (None, "-", "—")
        current_contractor = getattr(self.instance, "contractor", None)
        contractor_changed = contractor_provided and contractor != current_contractor
        try:
            saved = self.save_data(data)
            if saved:
                if contractor_changed:
                    cnt = get_expense_count_by_policy(saved.id)
                    is_new_policy = self.instance is None
                    should_show_dialog = not (is_new_policy and cnt > 0)
                    contractor_name = (saved.contractor or "").strip()
                    if should_show_dialog and contractor_name not in {"", "-", "—"}:
                        dialog = ContractorExpenseDialog(
                            saved, contractor_name, parent=self
                        )
                        if dialog.exec() == QDialog.Accepted:
                            selected_payments = dialog.get_selected_payments()
                            if selected_payments:
                                try:
                                    result = add_contractor_expense(
                                        saved, payments=selected_payments
                                    )
                                except ValueError as err:
                                    show_error(str(err))
                                else:
                                    if result.created:
                                        show_info("Расходы для контрагента созданы.")
                                    elif result.updated:
                                        show_info("Расходы для контрагента обновлены.")
                                    else:
                                        show_info(
                                            "Расходы для контрагента уже существовали."
                                        )
                self.saved_instance = saved
                self.accept()
        except DuplicatePolicyError as e:
            dlg = PolicyMergeDialog(
                e.existing_policy,
                data,
                draft_payments=self._draft_payments,
                first_payment_paid=self.first_payment_checkbox.isChecked(),
                parent=self,
            )
            if dlg.exec() == QDialog.Accepted:
                merged = dlg.get_merged_data()
                merged_payments = dlg.get_merged_payments()
                updated = update_policy(
                    e.existing_policy,
                    payments=merged_payments if merged_payments else None,
                    first_payment_paid=dlg.first_payment_checkbox.isChecked(),
                    **merged,
                )
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

    # ------------------------------------------------------------------
    # Payments
    # ------------------------------------------------------------------

    def _build_payments_section(self) -> None:
        group = QGroupBox("Платежи")
        vbox = QVBoxLayout(group)

        self.payments_table = QTableWidget(0, 4)
        self.payments_table.setHorizontalHeaderLabels([
            "Дата платежа",
            "Сумма",
            "Оплачен",
            "",
        ])
        self.payments_table.verticalHeader().setVisible(False)
        header = self.payments_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.payments_table.resizeColumnsToContents()
        self.payments_table.setMaximumHeight(240)
        self.payments_table.itemChanged.connect(self.on_payment_item_changed)
        vbox.addWidget(self.payments_table)

        if self.instance:
            existing = (
                Payment.active()
                .where(Payment.policy == self.instance)
                .order_by(Payment.payment_date)
            )
            for p in existing:
                self.add_payment_row(
                    {
                        "payment_date": p.payment_date,
                        "amount": float(p.amount),
                        "actual_payment_date": p.actual_payment_date,
                    }
                )

        hlayout = QHBoxLayout()
        self.pay_date_edit = QDateEdit()
        self.pay_date_edit.setCalendarPopup(True)
        self.pay_date_edit.setDate(QDate.currentDate())
        hlayout.addWidget(QLabel("Дата:"))
        hlayout.addWidget(self.pay_date_edit)

        self.pay_amount_edit = QLineEdit()
        hlayout.addWidget(QLabel("Сумма:"))
        hlayout.addWidget(self.pay_amount_edit)

        btn = QPushButton("Добавить платёж")
        btn.clicked.connect(self.on_add_payment)
        hlayout.addWidget(btn)
        vbox.addLayout(hlayout)

        self.add_section_widget(group)

    def add_payment_row(self, pay: dict) -> None:
        dt = pay.get("payment_date")
        amount = pay.get("amount")
        if not dt or amount is None:
            return
        row = self.payments_table.rowCount()
        was_blocked = self.payments_table.blockSignals(True)
        try:
            self.payments_table.insertRow(row)
            qd = QDate(dt.year, dt.month, dt.day)
            item_date = QTableWidgetItem(qd.toString("dd.MM.yyyy"))
            item_date.setData(Qt.UserRole, pay)
            self.payments_table.setItem(row, 0, item_date)
            self.payments_table.setItem(row, 1, QTableWidgetItem(f"{float(amount):.2f}"))
        finally:
            self.payments_table.blockSignals(was_blocked)
        chk = QCheckBox()
        chk.setChecked(bool(pay.get("actual_payment_date")))
        chk.stateChanged.connect(
            lambda state, p=pay: self.on_payment_paid_toggled(p, state)
        )
        self.payments_table.setCellWidget(row, 2, chk)
        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self.on_delete_payment)
        self.payments_table.setCellWidget(row, 3, del_btn)
        self._draft_payments.append(pay)

    def on_payment_paid_toggled(self, pay: dict, state: int) -> None:
        if pay is None:
            return
        pay["actual_payment_date"] = (
            pay["payment_date"] if state == Qt.Checked else None
        )

    def on_add_payment(self) -> None:
        qd = self.pay_date_edit.date()
        try:
            amt = float(normalize_number(self.pay_amount_edit.text()))
        except Exception:
            amt = 0.0
        self.add_payment_row(
            {
                "payment_date": qd.toPython(),
                "amount": amt,
                "actual_payment_date": None,
            }
        )
        self.pay_amount_edit.clear()

    def on_delete_payment(self) -> None:
        btn = self.sender()
        if not isinstance(btn, QPushButton):
            return
        for row in range(self.payments_table.rowCount()):
            if self.payments_table.cellWidget(row, 3) is btn:
                item = self.payments_table.item(row, 0)
                pay = item.data(Qt.UserRole) if item else None
                if pay in self._draft_payments:
                    self._draft_payments.remove(pay)
                self.payments_table.removeRow(row)
                break

    def on_payment_item_changed(self, item: QTableWidgetItem) -> None:
        if not item:
            return
        row = item.row()
        date_item = item if item.column() == 0 else self.payments_table.item(row, 0)
        if date_item is None:
            return
        pay = date_item.data(Qt.UserRole)
        if not isinstance(pay, dict):
            pay = {}
            date_item.setData(Qt.UserRole, pay)

        if item.column() == 0:
            text = item.text().strip()
            qdate = QDate.fromString(text, "dd.MM.yyyy")
            if qdate.isValid():
                pay["payment_date"] = qdate.toPython()
                was_blocked = self.payments_table.blockSignals(True)
                try:
                    item.setText(qdate.toString("dd.MM.yyyy"))
                    date_item.setData(Qt.UserRole, pay)
                finally:
                    self.payments_table.blockSignals(was_blocked)
            else:
                prev_date = pay.get("payment_date")
                if prev_date:
                    prev_qdate = QDate(prev_date.year, prev_date.month, prev_date.day)
                    was_blocked = self.payments_table.blockSignals(True)
                    try:
                        item.setText(prev_qdate.toString("dd.MM.yyyy"))
                    finally:
                        self.payments_table.blockSignals(was_blocked)
        elif item.column() == 1:
            text = item.text().strip()
            try:
                normalized = normalize_number(text) if text else None
                if normalized in (None, ""):
                    amount = 0.0
                else:
                    amount = float(normalized)
            except ValueError:
                amount = pay.get("amount", 0.0)
            pay["amount"] = amount
            was_blocked = self.payments_table.blockSignals(True)
            try:
                item.setText(f"{amount:.2f}")
            finally:
                self.payments_table.blockSignals(was_blocked)

    def _update_draft_payments_from_table(self) -> None:
        payments: list[dict] = []
        was_blocked = self.payments_table.blockSignals(True)
        try:
            for row in range(self.payments_table.rowCount()):
                date_item = self.payments_table.item(row, 0)
                amount_item = self.payments_table.item(row, 1)
                if date_item is None or amount_item is None:
                    continue
                pay = date_item.data(Qt.UserRole)
                if not isinstance(pay, dict):
                    pay = {}
                text_date = date_item.text().strip()
                qdate = QDate.fromString(text_date, "dd.MM.yyyy")
                if qdate.isValid():
                    pay["payment_date"] = qdate.toPython()
                    date_item.setText(qdate.toString("dd.MM.yyyy"))
                text_amount = amount_item.text().strip()
                try:
                    normalized = normalize_number(text_amount) if text_amount else None
                    if normalized in (None, ""):
                        amount = 0.0
                    else:
                        amount = float(normalized)
                except ValueError:
                    amount = pay.get("amount", 0.0)
                pay["amount"] = amount
                amount_item.setText(f"{amount:.2f}")
                date_item.setData(Qt.UserRole, pay)
                payments.append(pay)
        finally:
            self.payments_table.blockSignals(was_blocked)
        self._draft_payments = payments

