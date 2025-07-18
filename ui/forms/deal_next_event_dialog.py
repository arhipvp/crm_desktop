from __future__ import annotations

from datetime import date
from dateutil.relativedelta import relativedelta

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ui.common.date_utils import TypableDateEdit


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

