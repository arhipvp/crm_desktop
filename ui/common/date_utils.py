from __future__ import annotations

"""Date‑related helpers and widgets.

Fixed imports so they match PySide6 modules:
 • QRegularExpression → QtCore
 • QRegularExpressionValidator, QKeyEvent → QtGui
"""

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDateEdit, QLineEdit

# --- existing util functions (stubs, keep original implementation) ---


def is_date_empty(d): ...


def get_date_or_none(widget: QDateEdit):
    qd = widget.date()
    if not qd.isValid() or qd == widget.minimumDate():
        return None
    return qd.toPython()


def set_optional_date(widget, d): ...


def format_date(d):
    """Вернёт дату в формате ``dd.mm.yyyy`` либо ``"—"`` если даты нет."""
    if not d:
        return "—"
    return d.strftime("%d.%m.%Y")


class DateLineEdit(QLineEdit): ...


class TypableDateEdit(QDateEdit): ...


# ---------------------------------------------------------------------


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
