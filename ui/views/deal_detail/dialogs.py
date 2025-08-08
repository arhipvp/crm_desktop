from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox


class CloseDealDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Закрытие сделки")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Укажите причину закрытия:"))
        self.reason_edit = QTextEdit()
        layout.addWidget(self.reason_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_reason(self):
        return self.reason_edit.toPlainText().strip()
