from __future__ import annotations

"""Date‑related helpers and widgets.

Fixed imports so they match PySide6 modules:
 • QRegularExpression → QtCore
 • QRegularExpressionValidator, QKeyEvent → QtGui
 • QStyle, QToolButton → QtWidgets
"""

from datetime import date, datetime

from PySide6.QtCore import QDate, QRegularExpression, Qt
from PySide6.QtGui import QKeyEvent, QRegularExpressionValidator
from PySide6.QtWidgets import QDateEdit, QLineEdit, QStyle, QToolButton

# --- existing util functions (stubs, keep original implementation) ---

def is_date_empty(d):
    ...

def get_date_or_none(widget: QDateEdit):
    qd = widget.date()
    if hasattr(widget, "minimumDate") and qd == widget.minimumDate():
        return None
    return qd.toPython()


def set_optional_date(widget, d):
    ...

def format_date(d):
    """Возвращает дату в формате dd.MM.yyyy или "—"."""
    if not d:
        return "—"
    if isinstance(d, QDate):
        return d.toString("dd.MM.yyyy") if d.isValid() else "—"
    if isinstance(d, (date, datetime)):
        return d.strftime("%d.%m.%Y")
    return str(d)

class DateLineEdit(QLineEdit):
    ...

class TypableDateEdit(QDateEdit):
    ...

# ---------------------------------------------------------------------

class OptionalDateEdit(QDateEdit):
    """QDateEdit that allows clearing to None."""

    def __init__(self, parent=None, placeholder: str = "—"):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("dd.MM.yyyy")
        self.setSpecialValueText(placeholder)

        # store a sentinel minimum date to represent NULL
        self.setMinimumDate(QDate(1900, 1, 1))
        self.setDate(self.minimumDate())

        # clear button inside widget
        self._clear_btn = QToolButton(self)
        self._clear_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogCloseButton))
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.setToolTip("Очистить дату")
        self._clear_btn.clicked.connect(self.clear)
        self._reposition_btn()

    # exposed helper to fetch python date or None
    def date_or_none(self) -> date | None:
        return None if self.date() == self.minimumDate() else self.date().toPython()

    def clear(self):
        super().setDate(self.minimumDate())
        self.lineEdit().clear()

    # --- internal helpers ---
    def _reposition_btn(self):
        size = self.height() - 4
        frame = self.style().pixelMetric(QStyle.PM_DefaultFrameWidth)
        self._clear_btn.setFixedSize(size, size)
        self._clear_btn.move(self.width() - size - frame, (self.height() - size) // 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_btn()

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.clear()
        else:
            super().keyPressEvent(e)

# --- NEW: Add universal date helper here ---

def add_year_minus_one_day(qdate: QDate) -> QDate:
    """
    Вернёт дату через год минус день от переданной qdate.
    Если дата невалидна — возвращает пустую QDate().
    """
    if not qdate or not qdate.isValid():
        return QDate()
    return qdate.addYears(1).addDays(-1)

__all__ = [
    "is_date_empty",
    "get_date_or_none",
    "set_optional_date",
    "format_date",
    "DateLineEdit",
    "TypableDateEdit",
    "OptionalDateEdit",
    "add_year_minus_one_day",  # обязательно добавь в __all__
]



def parse_date_str(text: str) -> QDate:
    """Парсит строку dd.mm.yyyy в QDate. Невалидная строка → QDate()."""
    try:
        return QDate.fromString(text.strip(), "dd.MM.yyyy")
    except Exception:
        return QDate()

def to_qdate(d: date | None) -> QDate:
    """Преобразует date в QDate или возвращает пустую QDate()."""
    return QDate(d.year, d.month, d.day) if d else QDate()
