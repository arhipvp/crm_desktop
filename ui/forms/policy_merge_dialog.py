from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
)

from database.models import Policy


class PolicyMergeDialog(QDialog):
    def __init__(self, existing: Policy, new_data: dict, parent=None):
        super().__init__(parent)
        self.existing = existing
        self.new_data = new_data
        self.setWindowTitle("Объединение полиса")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([
            "Поле",
            "Текущее",
            "Новое значение",
        ])
        layout.addWidget(self.table)

        for field, new_val in new_data.items():
            old_val = getattr(existing, field, None)
            if str(old_val or "") == str(new_val or ""):
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(field))
            self.table.setItem(
                row, 1, QTableWidgetItem("" if old_val is None else str(old_val))
            )
            edit = QLineEdit("" if new_val is None else str(new_val))
            self.table.setCellWidget(row, 2, edit)

        btns = QHBoxLayout()
        self.merge_btn = QPushButton("Объединить")
        self.merge_btn.clicked.connect(self.accept)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(self.merge_btn)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def get_merged_data(self) -> dict:
        data = {}
        for row in range(self.table.rowCount()):
            field = self.table.item(row, 0).text()
            widget = self.table.cellWidget(row, 2)
            value = widget.text().strip()
            data[field] = value or None
        return data
