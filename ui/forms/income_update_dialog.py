from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHBoxLayout,
)
from PySide6.QtCore import Qt


class IncomeUpdateDialog(QDialog):
    """Диалог подтверждения обновления дохода."""

    def __init__(self, existing, new_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Обновить данные в доходе?")
        self.choice = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Обновить данные в доходе?"))

        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Поле", "Текущее", "Новое"])
        for field, new_val in new_data.items():
            old_val = getattr(existing, field, None)
            if str(old_val or "") == str(new_val or ""):
                continue
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(field.replace("_", " ").capitalize()))
            table.setItem(row, 1, QTableWidgetItem("" if old_val is None else str(old_val)))
            table.setItem(row, 2, QTableWidgetItem("" if new_val is None else str(new_val)))
        table.resizeColumnsToContents()
        layout.addWidget(table)

        btns = QHBoxLayout()
        update_btn = QPushButton("Обновить")
        new_btn = QPushButton("Создать новый")
        cancel_btn = QPushButton("Отмена")
        update_btn.clicked.connect(lambda: self._set_choice("update"))
        new_btn.clicked.connect(lambda: self._set_choice("new"))
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(new_btn)
        btns.addWidget(update_btn)
        layout.addLayout(btns)

    # ------------------------------------------------------------------
    def _set_choice(self, choice: str):
        self.choice = choice
        self.accept()
