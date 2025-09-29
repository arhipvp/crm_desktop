import base64
import binascii

from PySide6.QtCore import QByteArray
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
from ui import settings as ui_settings


SETTINGS_KEY = "client_import_dialog"


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

        self._restore_geometry()

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

    def accept(self):
        self._save_geometry()
        super().accept()

    def reject(self):
        self._save_geometry()
        super().reject()

    def closeEvent(self, event):
        self._save_geometry()
        super().closeEvent(event)

    def _restore_geometry(self):
        settings = ui_settings.get_window_settings(SETTINGS_KEY)
        geometry_b64 = settings.get("geometry") if isinstance(settings, dict) else None
        if not geometry_b64:
            return

        try:
            geometry_data = base64.b64decode(geometry_b64)
        except (ValueError, binascii.Error, TypeError):
            return

        if geometry_data:
            self.restoreGeometry(QByteArray(geometry_data))

    def _save_geometry(self):
        geometry = bytes(self.saveGeometry())
        geometry_b64 = base64.b64encode(geometry).decode("ascii")
        ui_settings.set_window_settings(SETTINGS_KEY, {"geometry": geometry_b64})
