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
)
from PySide6.QtGui import QColor, QDoubleValidator
from PySide6.QtCore import Qt, QDate
import peewee

from services.client_service import get_client_by_id
from services.deal_service import get_deal_by_id
from services.validators import normalize_number

from ui.common.combo_helpers import create_client_combobox, create_deal_combobox
from ui.common.date_utils import OptionalDateEdit, to_qdate

from database.models import Policy


class PolicyMergeDialog(QDialog):
    def __init__(self, existing: Policy, new_data: dict, parent=None):
        super().__init__(parent)
        self.existing = existing
        self.new_data = new_data
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
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Поле", "Текущее", "Новое значение", "Итоговое"]
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
                if new_val is not None:
                    idx = edit.findData(int(new_val))
                    if idx >= 0:
                        edit.setCurrentIndex(idx)
                edit.currentIndexChanged.connect(
                    lambda _=None, r=row, f=field: self._update_final(r, f)
                )
            elif field == "deal_id":
                edit = create_deal_combobox()
                if new_val is not None:
                    idx = edit.findData(int(new_val))
                    if idx >= 0:
                        edit.setCurrentIndex(idx)
                edit.currentIndexChanged.connect(
                    lambda _=None, r=row, f=field: self._update_final(r, f)
                )
            elif field in {"start_date", "end_date"}:
                edit = OptionalDateEdit()
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
                edit.setValidator(QDoubleValidator())
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

        self.table.resizeColumnsToContents()
        self._apply_filter()

        btns = QHBoxLayout()
        self.merge_btn = QPushButton("Объединить")
        self.merge_btn.clicked.connect(self.accept)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(self.merge_btn)
        btns.addWidget(cancel)
        layout.addLayout(btns)

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
        elif isinstance(widget, OptionalDateEdit):
            val = widget.date_or_none()
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
            item.setBackground(QColor("#fff0b3") if changed else QColor())
            widget.setStyleSheet("background:#fff0b3;" if changed else "")
            key_item = self.table.item(row, 0)
            if key_item is not None:
                key_item.setData(Qt.UserRole + 1, changed)
        self._apply_filter()

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
            if isinstance(widget, OptionalDateEdit):
                data[field] = widget.date_or_none()
                continue
            if isinstance(widget, QSpinBox):
                v = widget.value()
                data[field] = None if v == widget.minimum() else v
                continue

            text = widget.text().strip()
            if text == "":
                data[field] = None
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
