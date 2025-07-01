from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
)
from PySide6.QtCore import Qt

from services.client_service import get_client_by_id
from services.deal_service import get_deal_by_id

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
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Поле", "Текущее", "Новое значение", "Итоговое"]
        )
        layout.addWidget(self.table)

        for field, new_val in new_data.items():
            old_val = getattr(existing, field, None)
            if str(old_val or "") == str(new_val or ""):
                continue
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
            edit = QLineEdit("" if new_val is None else str(new_val))
            self.table.setCellWidget(row, 2, edit)
            final = QTableWidgetItem()
            self.table.setItem(row, 3, final)
            self._update_final(row, field)
            edit.textChanged.connect(lambda _=None, r=row, f=field: self._update_final(r, f))

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
        return str(value)

    def _update_final(self, row: int, field: str) -> None:
        widget = self.table.cellWidget(row, 2)
        text = widget.text().strip()
        final_val = text if text else getattr(self.existing, field, None)
        item = self.table.item(row, 3)
        if item is not None:
            item.setText(self._display_value(field, final_val))

    def get_merged_data(self) -> dict:
        data = {}
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            field = item.data(Qt.UserRole) if item is not None else None
            if not field:
                continue
            widget = self.table.cellWidget(row, 2)
            value = widget.text().strip()
            data[field] = value or None
        return data
