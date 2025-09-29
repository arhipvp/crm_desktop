import base64

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QComboBox, QPushButton, QHBoxLayout

from ui import settings as ui_settings


SETTINGS_KEY = "column_mapping_dialog"


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
        self.premium_cb = QComboBox()
        self.type_cb = QComboBox()
        self.channel_cb = QComboBox()

        for cb in (
            self.policy_cb,
            self.period_cb,
            self.amount_cb,
            self.premium_cb,
            self.type_cb,
            self.channel_cb,
        ):
            cb.addItems(columns)

        if "НОМЕР ПОЛИСА" in columns:
            self.policy_cb.setCurrentText("НОМЕР ПОЛИСА")
        if "НАЧИСЛЕНИЕ,С-ПО" in columns:
            self.period_cb.setCurrentText("НАЧИСЛЕНИЕ,С-ПО")
        if "arhvp" in columns:
            self.amount_cb.setCurrentText("arhvp")
        if "ПРЕМИЯ,РУБ." in columns:
            self.premium_cb.setCurrentText("ПРЕМИЯ,РУБ.")
        if "ПРОДУКТ" in columns:
            self.type_cb.setCurrentText("ПРОДУКТ")
        if "Источник" in columns:
            self.channel_cb.setCurrentText("Источник")

        form.addRow("Номер полиса", self.policy_cb)
        form.addRow("Период", self.period_cb)
        form.addRow("Сумма", self.amount_cb)
        form.addRow("Премия", self.premium_cb)
        form.addRow("Тип страхования", self.type_cb)
        form.addRow("Канал продаж", self.channel_cb)
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

        self._restore_geometry()

    def get_mapping(self) -> dict[str, str]:
        return {
            "policy_number": self.policy_cb.currentText(),
            "period": self.period_cb.currentText(),
            "amount": self.amount_cb.currentText(),
            "premium": self.premium_cb.currentText(),
            "insurance_type": self.type_cb.currentText(),
            "sales_channel": self.channel_cb.currentText(),
        }

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
