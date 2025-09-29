import base64

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHBoxLayout,
)
from PySide6.QtCore import QByteArray, Qt

from ui import settings as ui_settings


SETTINGS_KEY = "income_update_dialog"


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

        self._restore_geometry()

    # ------------------------------------------------------------------
    def _set_choice(self, choice: str):
        self.choice = choice
        self.accept()

    def accept(self):  # noqa: D401 - Qt override
        self._save_geometry()
        super().accept()

    def reject(self):  # noqa: D401 - Qt override
        self._save_geometry()
        super().reject()

    def closeEvent(self, event):  # noqa: D401 - Qt override
        self._save_geometry()
        super().closeEvent(event)

    def _restore_geometry(self) -> None:
        settings = ui_settings.get_window_settings(SETTINGS_KEY)
        geometry_b64 = settings.get("geometry")
        if not geometry_b64:
            return
        try:
            geometry_bytes = base64.b64decode(geometry_b64.encode("ascii"))
        except Exception:  # pragma: no cover - защита от повреждённых данных
            return
        self.restoreGeometry(QByteArray(geometry_bytes))

    def _save_geometry(self) -> None:
        geometry = base64.b64encode(bytes(self.saveGeometry())).decode("ascii")
        settings = ui_settings.get_window_settings(SETTINGS_KEY)
        settings["geometry"] = geometry
        ui_settings.set_window_settings(SETTINGS_KEY, settings)
