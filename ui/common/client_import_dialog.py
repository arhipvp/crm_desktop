from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from database.models import Client
from services.validators import normalize_phone


class ClientImportDialog(QDialog):
    def __init__(self, suggested_name="", suggested_phone="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выбор или создание клиента")
        self.setMinimumWidth(400)

        self.name_edit = QLineEdit(suggested_name)
        self.phone_edit = QLineEdit(suggested_phone)

        self.phone_edit.setPlaceholderText("Введите номер телефона")

        self.confirm_btn = QPushButton("Использовать")
        self.cancel_btn = QPushButton("Отмена")

        layout = QVBoxLayout()
        layout.addWidget(QLabel("ФИО клиента:"))
        layout.addWidget(self.name_edit)
        layout.addWidget(QLabel("Телефон:"))
        layout.addWidget(self.phone_edit)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.confirm_btn)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self.confirm_btn.clicked.connect(self._on_confirm)
        self.cancel_btn.clicked.connect(self.reject)

        self.client = None

    def _on_confirm(self):
        name = self.name_edit.text().strip()
        try:
            phone = normalize_phone(self.phone_edit.text())
        except ValueError as e:
            QMessageBox.warning(self, "Ошибка", str(e))
            return

        if not name or not phone:
            QMessageBox.warning(self, "Ошибка", "ФИО и телефон обязательны")
            return

        self.client, created = Client.get_or_create(
            name=name, defaults={"phone": phone}
        )

        if not created and not self.client.phone and phone:
            self.client.phone = phone
            self.client.save()

        self.accept()
