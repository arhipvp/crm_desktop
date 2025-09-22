from __future__ import annotations

"""Date‑related helpers and widgets.

Fixed imports so they match PySide6 modules:
 • QRegularExpression → QtCore
 • QRegularExpressionValidator, QKeyEvent → QtGui
"""

from datetime import date

from PySide6.QtCore import QDate, QEvent, QPoint, Qt, QObject
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDateEdit, QLineEdit


# Значение, используемое в QDateEdit как «пустая» дата.
OPTIONAL_DATE_MIN = QDate(2000, 1, 1)

# --- existing util functions (stubs, keep original implementation) ---


def is_date_empty(d): ...


def get_date_or_none(widget: QDateEdit | None):
    if widget is None:
        return None

    qd = widget.date()
    if not qd.isValid():
        return None
    min_date = widget.minimumDate()
    if min_date.isValid() and qd == min_date:
        return None
    return qd.toPython()


def configure_optional_date_edit(widget: QDateEdit | None) -> None:
    """Настраивает QDateEdit так, чтобы минимальная дата обозначала «пусто»."""

    if widget is None:
        return

    widget.setMinimumDate(OPTIONAL_DATE_MIN)
    widget.setDate(widget.minimumDate())

    # навешиваем обработчики очистки через Delete / контекстное меню
    _OptionalDateEditHelper.ensure_for(widget)


def clear_optional_date(widget: QDateEdit | None) -> None:
    """Сбрасывает QDateEdit к его минимальной дате."""

    if widget is None:
        return

    widget.setDate(widget.minimumDate())


class _OptionalDateEditHelper(QObject):
    """Навешивает на QDateEdit горячие клавиши и контекстное меню для очистки."""

    _ATTRIBUTE = "_optional_date_helper"

    def __init__(self, widget: QDateEdit):
        super().__init__(widget)
        self._widget = widget

        widget.installEventFilter(self)

        line_edit = widget.lineEdit()
        if line_edit is not None:
            line_edit.installEventFilter(self)
            line_edit.setContextMenuPolicy(Qt.CustomContextMenu)
            line_edit.customContextMenuRequested.connect(self._show_context_menu)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------
    @classmethod
    def ensure_for(cls, widget: QDateEdit) -> None:
        if getattr(widget, cls._ATTRIBUTE, None) is not None:
            return

        helper = cls(widget)
        setattr(widget, cls._ATTRIBUTE, helper)

    # ------------------------------------------------------------------
    # Event filter / menu
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):  # noqa: N802 (Qt signature)
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Delete:
            if event.modifiers() in (Qt.NoModifier, Qt.KeypadModifier):
                clear_optional_date(self._widget)
                event.accept()
                return True
        return super().eventFilter(obj, event)

    def _show_context_menu(self, pos: QPoint) -> None:
        line_edit = self._widget.lineEdit()
        if line_edit is None:
            return

        menu = line_edit.createStandardContextMenu()
        menu.addSeparator()
        action = menu.addAction("Очистить дату")

        def _clear():
            clear_optional_date(self._widget)

        action.triggered.connect(_clear)  # type: ignore[arg-type]
        menu.exec(line_edit.mapToGlobal(pos))


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
    "OPTIONAL_DATE_MIN",
    "configure_optional_date_edit",
    "clear_optional_date",
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
