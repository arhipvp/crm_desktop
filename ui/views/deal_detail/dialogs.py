import base64

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox

import ui.settings


SETTINGS_KEY = "close_deal_dialog"


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

        self._restore_geometry()

    def get_reason(self):
        return self.reason_edit.toPlainText().strip()

    def _restore_geometry(self):
        geometry_b64 = ui.settings.get_window_settings(SETTINGS_KEY).get("geometry")
        if not geometry_b64:
            return
        try:
            geometry_bytes = base64.b64decode(geometry_b64)
        except Exception:  # pragma: no cover - восстановление необязательно
            return
        self.restoreGeometry(QByteArray(geometry_bytes))

    def _save_geometry(self):
        try:
            geometry_bytes = bytes(self.saveGeometry())
        except Exception:  # pragma: no cover - сохранение необязательно
            return
        geometry_b64 = base64.b64encode(geometry_bytes).decode("ascii")
        settings = ui.settings.get_window_settings(SETTINGS_KEY)
        settings["geometry"] = geometry_b64
        ui.settings.set_window_settings(SETTINGS_KEY, settings)

    def accept(self):
        self._save_geometry()
        super().accept()

    def reject(self):
        self._save_geometry()
        super().reject()

    def closeEvent(self, event):
        self._save_geometry()
        super().closeEvent(event)
