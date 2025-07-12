from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QComboBox, QPushButton, QHBoxLayout


class ColumnMappingDialog(QDialog):
    """Dialog to map RESO table columns to policy fields."""

    def __init__(self, columns: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Сопоставление столбцов")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.policy_cb = QComboBox()
        self.period_cb = QComboBox()
        self.amount_cb = QComboBox()
        for cb in (self.policy_cb, self.period_cb, self.amount_cb):
            cb.addItems(columns)
        if "НОМЕР ПОЛИСА" in columns:
            self.policy_cb.setCurrentText("НОМЕР ПОЛИСА")
        if "НАЧИСЛЕНИЕ,С-ПО" in columns:
            self.period_cb.setCurrentText("НАЧИСЛЕНИЕ,С-ПО")
        if "arhvp" in columns:
            self.amount_cb.setCurrentText("arhvp")
        form.addRow("Номер полиса", self.policy_cb)
        form.addRow("Период", self.period_cb)
        form.addRow("Сумма", self.amount_cb)
        layout.addLayout(form)
        btns = QHBoxLayout()
        ok_btn = QPushButton("Продолжить")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    def get_mapping(self) -> dict[str, str]:
        return {
            "policy_number": self.policy_cb.currentText(),
            "period": self.period_cb.currentText(),
            "amount": self.amount_cb.currentText(),
        }
