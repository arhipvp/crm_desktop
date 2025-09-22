from __future__ import annotations

"""Date‑related helpers and widgets.

Fixed imports so they match PySide6 modules:
 • QRegularExpression → QtCore
 • QRegularExpressionValidator, QKeyEvent → QtGui
"""

from datetime import date

from typing import Optional

from PySide6.QtCore import QDate, QEvent, QPoint, Qt, QObject
from PySide6.QtGui import QAction, QKeyEvent
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
        self._line_edit: Optional[QLineEdit] = widget.lineEdit()
        self._clear_action: Optional[QAction] = None

        widget.installEventFilter(self)

        if self._line_edit is not None:
            self._line_edit.installEventFilter(self)
            self._line_edit.setClearButtonEnabled(True)
            self._line_edit.textChanged.connect(self._handle_line_edit_text_changed)
            self._line_edit.setContextMenuPolicy(Qt.CustomContextMenu)
            self._line_edit.customContextMenuRequested.connect(self._show_context_menu)
            self._hook_clear_button_action()

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
        if event.type() == QEvent.KeyPress and event.key() in (
            Qt.Key_Delete,
            Qt.Key_Backspace,
        ):
            if event.modifiers() in (Qt.NoModifier, Qt.KeypadModifier):
                clear_optional_date(self._widget)
                event.accept()
                return True
        return super().eventFilter(obj, event)

    def _show_context_menu(self, pos: QPoint) -> None:
        if self._line_edit is None:
            return

        menu = self._line_edit.createStandardContextMenu()
        menu.addSeparator()
        action = menu.addAction("Очистить дату")

        def _clear():
            clear_optional_date(self._widget)

        action.triggered.connect(_clear)  # type: ignore[arg-type]
        menu.exec(self._line_edit.mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _handle_line_edit_text_changed(self, text: str) -> None:
        if text:
            return
        if self._widget.date() == self._widget.minimumDate():
            return
        clear_optional_date(self._widget)

    def _hook_clear_button_action(self) -> None:
        if self._line_edit is None:
            return

        action = self._find_clear_action(self._line_edit)
        if action is None:
            return

        self._clear_action = action
        self._clear_action.triggered.connect(self._on_clear_button_triggered)

    @staticmethod
    def _find_clear_action(line_edit: QLineEdit) -> Optional[QAction]:
        # Qt создаёт действие "qt_edit_clear_action" для стандартной кнопки очистки.
        for action in line_edit.actions():
            if action.objectName() == "qt_edit_clear_action":
                return action
        return None

    def _on_clear_button_triggered(self) -> None:
        clear_optional_date(self._widget)


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
