from datetime import date

import pytest
from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QDateEdit

from ui.common.date_utils import configure_optional_date_edit, get_date_or_none


@pytest.fixture
def optional_date_edit(qapp):
    edit = QDateEdit()
    edit.setCalendarPopup(True)
    edit.setSpecialValueText("—")
    configure_optional_date_edit(edit)
    edit.setDate(QDate(2024, 1, 2))
    return edit


def test_configure_optional_date_edit_enables_clear_button(optional_date_edit):
    line_edit = optional_date_edit.lineEdit()
    assert line_edit is not None
    assert line_edit.isClearButtonEnabled()


def test_delete_key_clears_optional_date(optional_date_edit):
    line_edit = optional_date_edit.lineEdit()
    assert line_edit is not None

    assert get_date_or_none(optional_date_edit) == date(2024, 1, 2)

    delete_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
    QApplication.sendEvent(line_edit, delete_event)

    assert get_date_or_none(optional_date_edit) is None


def test_backspace_key_clears_optional_date(optional_date_edit):
    optional_date_edit.setDate(QDate(2024, 2, 3))
    assert get_date_or_none(optional_date_edit) == date(2024, 2, 3)

    line_edit = optional_date_edit.lineEdit()
    assert line_edit is not None

    backspace_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Backspace, Qt.NoModifier)
    QApplication.sendEvent(line_edit, backspace_event)

    assert get_date_or_none(optional_date_edit) is None


def test_clear_button_clears_optional_date(optional_date_edit):
    line_edit = optional_date_edit.lineEdit()
    assert line_edit is not None

    optional_date_edit.setDate(QDate(2025, 5, 6))
    assert get_date_or_none(optional_date_edit) == date(2025, 5, 6)

    line_edit.clear()
    QApplication.processEvents()

    assert get_date_or_none(optional_date_edit) is None
