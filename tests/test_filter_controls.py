import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication
from ui.common.filter_controls import FilterControls


def test_filter_controls_hide_date_range(qtbot):
    fc = FilterControls(lambda: None, show_date_range=False)
    qtbot.addWidget(fc)
    assert fc._date_from is None
    assert fc._date_to is None
