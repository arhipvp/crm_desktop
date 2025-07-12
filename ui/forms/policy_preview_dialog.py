from PySide6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout


class PolicyPreviewDialog(QDialog):
    """Предпросмотр данных полиса RESO."""

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Предпросмотр полиса")
        layout = QVBoxLayout(self)

        self.table = QTableWidget(len(data), 2, self)
        self.table.setHorizontalHeaderLabels(["Поле", "Значение"])
        for row, (key, value) in enumerate(data.items()):
            self.table.setItem(row, 0, QTableWidgetItem(str(key)))
            self.table.setItem(row, 1, QTableWidgetItem("" if value is None else str(value)))
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        btns = QHBoxLayout()
        ok_btn = QPushButton("Продолжить", self)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена", self)
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)
