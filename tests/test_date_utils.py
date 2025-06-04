from datetime import date
from PySide6.QtCore import QDate
from ui.common.date_utils import format_date


def test_format_date_various():
    assert format_date(date(2025, 5, 10)) == "10.05.2025"
    assert format_date(QDate(2025, 6, 1)) == "01.06.2025"
    assert format_date(None) == "—"
