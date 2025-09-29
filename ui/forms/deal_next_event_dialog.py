from __future__ import annotations

import base64
import binascii

from datetime import date
from dateutil.relativedelta import relativedelta

from PySide6.QtCore import QDate, QByteArray
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ui import settings as ui_settings
from ui.common.date_utils import TypableDateEdit


SETTINGS_KEY = "deal_next_event_dialog"


class DealNextEventDialog(QDialog):
    """Dialog to postpone deal reminder until selected event."""

    def __init__(self, events: list[tuple[str, date]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выбор события")
        self.selected_date: date | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Следующие события:"))

        self.combo = QComboBox()
        for label, dt in events:
            self.combo.addItem(f"{label} — {dt:%d.%m.%Y}", dt)
        self.combo.currentIndexChanged.connect(self._on_event_changed)
        layout.addWidget(self.combo)

        layout.addWidget(QLabel("Дата напоминания:"))
        self.date_edit = TypableDateEdit()
        layout.addWidget(self.date_edit)

        btns = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(ok_btn)
        layout.addLayout(btns)

        if events:
            self._on_event_changed()

        self._restore_geometry()

    # ------------------------------------------------------------------
    def _on_event_changed(self):
        idx = self.combo.currentIndex()
        dt = self.combo.itemData(idx)
        if isinstance(dt, date):
            remind = dt - relativedelta(months=1)
            self.date_edit.setDate(QDate(remind.year, remind.month, remind.day))

    # ------------------------------------------------------------------
    def get_reminder_date(self) -> date:
        qd = self.date_edit.date()
        return qd.toPython()

    # ------------------------------------------------------------------
    def accept(self):
        self._save_geometry()
        super().accept()

    # ------------------------------------------------------------------
    def reject(self):
        self._save_geometry()
        super().reject()

    # ------------------------------------------------------------------
    def closeEvent(self, event):
        self._save_geometry()
        super().closeEvent(event)

    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    def _save_geometry(self):
        geometry = bytes(self.saveGeometry())
        geometry_b64 = base64.b64encode(geometry).decode("ascii")
        ui_settings.set_window_settings(SETTINGS_KEY, {"geometry": geometry_b64})

