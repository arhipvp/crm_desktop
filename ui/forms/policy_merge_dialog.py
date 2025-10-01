import base64
from datetime import date

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QComboBox,
    QSpinBox,
    QGroupBox,
    QDateEdit,
    QHeaderView,
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt, QDate, QByteArray
import peewee

from services.clients import get_client_by_id
from services.deal_service import get_deal_by_id, get_deals_by_client_id
from services.validators import normalize_number, normalize_policy_number

from ui.common.combo_helpers import (
    create_client_combobox,
    create_deal_combobox,
    populate_combo,
)
from ui.common.date_utils import (
    configure_optional_date_edit,
    get_date_or_none,
    to_qdate,
)

from database.models import Policy, Payment
from ui import settings as ui_settings
from ui.forms.payment_helpers import resolve_actual_payment_date


class PolicyMergeDialog(QDialog):
    SETTINGS_KEY = "policy_merge_dialog"

    def __init__(
        self,
        existing: Policy,
        new_data: dict,
        draft_payments: list[dict] | None = None,
        first_payment_paid: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.existing = existing
        self.new_data = new_data
        self._draft_payments = draft_payments or []
        self._first_payment_paid = first_payment_paid
        self.setWindowTitle("Объединение полиса")
        # окно объединения было довольно узким, увеличиваем стандартный размер
        self.setMinimumSize(640, 400)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Измените значения в колонке 'Новое значение'.\n"
                "Итоговое значение отображается в последней колонке."
            )
        )
        self.show_only_changes_cb = QCheckBox("Показывать только изменения")
        self.show_only_changes_cb.toggled.connect(self._apply_filter)
        layout.addWidget(self.show_only_changes_cb)
        window_settings = ui_settings.get_window_settings(self.SETTINGS_KEY)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Поле", "Текущее", "Новое значение", "Итоговое"]
        )
        table_header = self.table.horizontalHeader()
        table_header.setSectionResizeMode(QHeaderView.Interactive)
        self._apply_widths_to_table(
            self.table,
            (window_settings or {}).get("table_column_widths"),
        )
        layout.addWidget(self.table)

        for field, new_val in new_data.items():
            old_val = getattr(existing, field, None)
            row = self.table.rowCount()
            self.table.insertRow(row)
            item = QTableWidgetItem(self._prettify_field(field))
            item.setData(Qt.UserRole, field)
            self.table.setItem(row, 0, item)
            self.table.setItem(
                row,
                1,
                QTableWidgetItem(self._display_value(field, old_val)),
            )

            model_field = Policy._meta.fields.get(field)

            if field == "client_id":
                edit: QComboBox = create_client_combobox()
                self.client_combo = edit
                if new_val is not None:
                    idx = edit.findData(int(new_val))
                    if idx >= 0:
                        edit.setCurrentIndex(idx)
                edit.currentIndexChanged.connect(
                    lambda _=None, r=row, f=field: self._update_final(r, f)
                )
                edit.currentIndexChanged.connect(self._on_client_changed)
            elif field == "deal_id":
                edit = create_deal_combobox()
                self.deal_combo = edit
                self.deal_row = row
                if new_val is not None:
                    idx = edit.findData(int(new_val))
                    if idx >= 0:
                        edit.setCurrentIndex(idx)
                edit.currentIndexChanged.connect(
                    lambda _=None, r=row, f=field: self._update_final(r, f)
                )
            elif field in {"start_date", "end_date"}:
                edit = QDateEdit()
                edit.setCalendarPopup(True)
                edit.setSpecialValueText("—")
                configure_optional_date_edit(edit)
                if isinstance(new_val, date):
                    edit.setDate(to_qdate(new_val))
                edit.dateChanged.connect(
                    lambda _=None, r=row, f=field: self._update_final(r, f)
                )
            elif isinstance(
                model_field,
                (peewee.IntegerField, peewee.AutoField, peewee.BigIntegerField, peewee.SmallIntegerField),
            ):
                spin = QSpinBox()
                spin.setMinimum(-1)
                spin.setSpecialValueText("")
                if new_val is not None:
                    try:
                        spin.setValue(int(new_val))
                    except Exception:
                        spin.setValue(-1)
                edit = spin
                spin.valueChanged.connect(
                    lambda _=None, r=row, f=field: self._update_final(r, f)
                )
            elif isinstance(model_field, peewee.FloatField):
                edit = QLineEdit("" if new_val is None else str(new_val))
                edit.textChanged.connect(
                    lambda _=None, r=row, f=field: self._update_final(r, f)
                )
            else:
                edit = QLineEdit("" if new_val is None else str(new_val))
                edit.setPlaceholderText("оставить без изменений")
                edit.textChanged.connect(
                    lambda _=None, r=row, f=field: self._update_final(r, f)
                )

            self.table.setCellWidget(row, 2, edit)
            final = QTableWidgetItem()
            self.table.setItem(row, 3, final)
            self._update_final(row, field)

        if hasattr(self, "client_combo"):
            self._on_client_changed()

        self._apply_filter()

        self._build_payments_section(layout, window_settings)

        btns = QHBoxLayout()
        self.merge_btn = QPushButton("Объединить")
        self.merge_btn.clicked.connect(self.accept)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(self.merge_btn)
        btns.addWidget(cancel)
        layout.addLayout(btns)

        self._restore_geometry()
        self._apply_saved_column_widths()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _prettify_field(self, field: str) -> str:
        return field.replace("_", " ").capitalize()

    def _display_value(self, field: str, value):
        if value in (None, ""):
            return ""
        if field == "client_id":
            try:
                client = get_client_by_id(int(value))
                return client.name if client else str(value)
            except Exception:
                return str(value)
        if field == "deal_id":
            try:
                deal = get_deal_by_id(int(value))
                return str(deal) if deal else str(value)
            except Exception:
                return str(value)
        if isinstance(value, date):
            return value.strftime("%d.%m.%Y")
        return str(value)

    def _apply_filter(self) -> None:
        show_only = self.show_only_changes_cb.isChecked()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is None:
                continue
            changed = bool(item.data(Qt.UserRole + 1))
            self.table.setRowHidden(row, show_only and not changed)

    def _update_final(self, row: int, field: str) -> None:
        widget = self.table.cellWidget(row, 2)
        if isinstance(widget, QComboBox):
            val = widget.currentData()
        elif isinstance(widget, QDateEdit):
            val = get_date_or_none(widget)
        elif isinstance(widget, QSpinBox):
            v = widget.value()
            val = None if v == widget.minimum() else v
        else:
            text = widget.text().strip()
            val = text if text else None

        final_val = val if val is not None else getattr(self.existing, field, None)
        item = self.table.item(row, 3)
        if item is not None:
            item.setText(self._display_value(field, final_val))
            old_val = getattr(self.existing, field, None)
            changed = str(final_val) != str(old_val)
            item.setBackground(QColor("#fff0b3") if changed else Qt.white)
            widget.setStyleSheet("background:#fff0b3;" if changed else "")
            key_item = self.table.item(row, 0)
            if key_item is not None:
                key_item.setData(Qt.UserRole + 1, changed)
        self._apply_filter()

    def _on_client_changed(self) -> None:
        if not hasattr(self, "deal_combo"):
            return
        client_id = self.client_combo.currentData()
        deals = (
            list(get_deals_by_client_id(client_id))
            if client_id is not None
            else []
        )
        current_deal_id = self.deal_combo.currentData()
        populate_combo(
            self.deal_combo,
            deals,
            label_func=lambda d: f"{d.client.name} - {d.description} ",
            id_attr="id",
            placeholder="— Сделка —",
        )
        if current_deal_id in [d.id for d in deals]:
            idx = self.deal_combo.findData(current_deal_id)
            if idx >= 0:
                self.deal_combo.setCurrentIndex(idx)
        self._update_final(self.deal_row, "deal_id")

    # ------------------------------------------------------------------
    # Payments
    # ------------------------------------------------------------------

    def _build_payments_section(
        self, layout: QVBoxLayout, window_settings: dict | None = None
    ) -> None:
        group = QGroupBox("Платежи")
        vbox = QVBoxLayout(group)
        self.payments_table = QTableWidget(0, 4)
        self.payments_table.setHorizontalHeaderLabels([
            "Дата платежа",
            "Сумма",
            "Оплачен",
            "",
        ])
        payments_header = self.payments_table.horizontalHeader()
        payments_header.setSectionResizeMode(QHeaderView.Interactive)
        if window_settings is None:
            window_settings = ui_settings.get_window_settings(self.SETTINGS_KEY)
        self._apply_widths_to_table(
            self.payments_table,
            (window_settings or {}).get("payments_column_widths"),
        )
        vbox.addWidget(self.payments_table)

        # существующие платежи из БД
        for p in (
            Payment.active()
            .where(Payment.policy == self.existing)
            .order_by(Payment.payment_date)
        ):
            self._insert_payment_row(
                p.payment_date, float(p.amount), p.actual_payment_date
            )

        # черновики платежей (новые)
        for p in self._draft_payments:
            self._insert_payment_row(
                p.get("payment_date"),
                p.get("amount"),
                p.get("actual_payment_date"),
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

        self.first_payment_checkbox = QCheckBox("Первый платёж уже оплачен")
        if not self._first_payment_paid:
            first = (
                Payment.active()
                .where(Payment.policy == self.existing)
                .order_by(Payment.payment_date)
                .first()
            )
            self._first_payment_paid = bool(first and first.actual_payment_date)
        self.first_payment_checkbox.setChecked(self._first_payment_paid)
        vbox.addWidget(self.first_payment_checkbox)

        layout.addWidget(group)

    def _insert_payment_row(self, dt, amount, actual_payment_date=None) -> None:
        """Добавить строку платежа. В UserRole ячейки даты храним фактическую дату оплаты."""
        if dt is None or amount is None:
            return
        row = self.payments_table.rowCount()
        self.payments_table.insertRow(row)

        # дата платежа (планируемая)
        qd = QDate(dt.year, dt.month, dt.day)
        date_item = QTableWidgetItem(qd.toString("dd.MM.yyyy"))

        # сохранить фактическую дату оплаты (если есть) в UserRole
        if isinstance(actual_payment_date, date):
            date_item.setData(Qt.UserRole, QDate(actual_payment_date.year, actual_payment_date.month, actual_payment_date.day))
        else:
            date_item.setData(Qt.UserRole, None)

        self.payments_table.setItem(row, 0, date_item)

        # сумма
        try:
            amt = float(amount)
        except Exception:
            amt = 0.0
        self.payments_table.setItem(row, 1, QTableWidgetItem(f"{amt:.2f}"))

        # чекбокс "оплачен" (истина, если есть фактическая дата)
        chk = QCheckBox()
        chk.setChecked(bool(actual_payment_date))
        self.payments_table.setCellWidget(row, 2, chk)

        # кнопка удаления
        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(lambda _, r=row: self.on_delete_payment(r))
        self.payments_table.setCellWidget(row, 3, del_btn)

    def on_add_payment(self) -> None:
        qd = self.pay_date_edit.date()
        amt = float(normalize_number(self.pay_amount_edit.text()))
        self._insert_payment_row(qd.toPython(), amt, None)
        self.pay_amount_edit.clear()

    def on_delete_payment(self, row: int) -> None:
        if 0 <= row < self.payments_table.rowCount():
            self.payments_table.removeRow(row)

    def get_merged_payments(self) -> list[dict]:
        """Вернуть итоговый список платежей после добавлений и удалений.

        Возвращаемые платежи отсортированы по дате, что упрощает дальнейшее
        сравнение и синхронизацию с базой данных.
        """
        payments: list[dict] = []
        for row in range(self.payments_table.rowCount()):
            date_item = self.payments_table.item(row, 0)
            amount_item = self.payments_table.item(row, 1)
            chk = self.payments_table.cellWidget(row, 2)
            if not date_item or not amount_item:
                continue

            qd = QDate.fromString(date_item.text(), "dd.MM.yyyy")
            if not qd.isValid():
                continue

            try:
                amount = float(amount_item.text())
            except Exception:
                continue

            # читаем фактическую дату оплаты из UserRole
            actual_dt = date_item.data(Qt.UserRole)
            stored_actual = actual_dt.toPython() if isinstance(actual_dt, QDate) else None
            is_checked = isinstance(chk, QCheckBox) and chk.isChecked()
            actual_payment_date = resolve_actual_payment_date(
                qd.toPython(), stored_actual, is_checked
            )

            payments.append(
                {
                    "payment_date": qd.toPython(),
                    "amount": amount,
                    "actual_payment_date": actual_payment_date,
                }
            )
        return sorted(payments, key=lambda p: p["payment_date"])

    def get_merged_data(self) -> dict:
        data = {}
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            field = item.data(Qt.UserRole) if item is not None else None
            if not field:
                continue
            widget = self.table.cellWidget(row, 2)

            if isinstance(widget, QComboBox):
                val = widget.currentData()
                data[field] = int(val) if val is not None else None
                continue
            if isinstance(widget, QDateEdit):
                data[field] = get_date_or_none(widget)
                continue
            if isinstance(widget, QSpinBox):
                v = widget.value()
                data[field] = None if v == widget.minimum() else v
                continue

            text = widget.text().strip()
            if text == "":
                data[field] = None
                continue

            if field == "policy_number":
                data[field] = normalize_policy_number(text)
                continue

            model_field = Policy._meta.fields.get(field)

            if isinstance(
                model_field,
                (peewee.IntegerField, peewee.AutoField, peewee.ForeignKeyField),
            ):
                try:
                    data[field] = int(normalize_number(text))
                except ValueError:
                    data[field] = None
            elif isinstance(model_field, peewee.FloatField):
                try:
                    data[field] = float(normalize_number(text))
                except ValueError:
                    data[field] = None
            elif isinstance(model_field, peewee.DateField):
                qd = QDate.fromString(text, "dd.MM.yyyy")
                data[field] = qd.toPython() if qd.isValid() else None
            else:
                data[field] = text

        return data

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def accept(self) -> None:  # type: ignore[override]
        self._save_geometry()
        super().accept()

    def reject(self) -> None:  # type: ignore[override]
        self._save_geometry()
        super().reject()

    def closeEvent(self, event):  # type: ignore[override]
        self._save_geometry()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def _apply_widths_to_table(self, table: QTableWidget, widths) -> bool:
        if not isinstance(widths, dict):
            return False
        header = table.horizontalHeader()
        applied = False
        for section in range(table.columnCount()):
            value = widths.get(str(section))
            if value is None:
                value = widths.get(section)
            if value is None:
                continue
            try:
                size = int(value)
            except (TypeError, ValueError):
                continue
            if size <= 0:
                continue
            header.resizeSection(section, size)
            applied = True
        return applied

    def _apply_saved_column_widths(self) -> None:
        settings = ui_settings.get_window_settings(self.SETTINGS_KEY)
        table_applied = self._apply_widths_to_table(
            self.table,
            (settings or {}).get("table_column_widths"),
        )
        payments_applied = self._apply_widths_to_table(
            self.payments_table,
            (settings or {}).get("payments_column_widths"),
        )
        if not table_applied:
            self.table.resizeColumnsToContents()
        if not payments_applied:
            self.payments_table.resizeColumnsToContents()

    def _restore_geometry(self) -> None:
        try:
            geometry_b64 = ui_settings.get_window_settings(self.SETTINGS_KEY).get("geometry")
            if geometry_b64:
                geometry_bytes = base64.b64decode(geometry_b64)
                self.restoreGeometry(QByteArray(geometry_bytes))
        except Exception:  # pragma: no cover - восстановление необязательно
            pass

    def _save_geometry(self) -> None:
        try:
            geometry = bytes(self.saveGeometry())
            geometry_b64 = base64.b64encode(geometry).decode("ascii")
            settings = ui_settings.get_window_settings(self.SETTINGS_KEY)
            settings["geometry"] = geometry_b64
            table_header = self.table.horizontalHeader()
            payments_header = self.payments_table.horizontalHeader()
            settings["table_column_widths"] = {
                str(i): int(table_header.sectionSize(i))
                for i in range(self.table.columnCount())
            }
            settings["payments_column_widths"] = {
                str(i): int(payments_header.sectionSize(i))
                for i in range(self.payments_table.columnCount())
            }
            ui_settings.set_window_settings(self.SETTINGS_KEY, settings)
        except Exception:  # pragma: no cover - сохранение не критично
            pass
