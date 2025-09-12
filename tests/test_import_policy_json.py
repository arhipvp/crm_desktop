import pytest
from PySide6.QtWidgets import QApplication, QDialog, QTabWidget, QWidget

from ui.main_window import MainWindow


def _create_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_open_import_policy_json_repeats_and_shows_message(monkeypatch):
    _create_app()

    outcomes = [QDialog.Accepted, QDialog.Rejected]
    created = []

    class DummyDlg:
        def __init__(self, parent=None):
            created.append(1)
        def exec(self):
            return outcomes.pop(0)

    monkeypatch.setattr('ui.main_window.ImportPolicyJsonForm', DummyDlg)

    def dummy_init_tabs(self):
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
    monkeypatch.setattr(MainWindow, 'init_tabs', dummy_init_tabs)
    monkeypatch.setattr(MainWindow, 'on_tab_changed', lambda self, index: None)

    mw = MainWindow()
    messages = []
    monkeypatch.setattr(mw.status_bar, 'showMessage', lambda msg, timeout=0: messages.append(msg))

    mw.open_import_policy_json()

    assert len(created) == 2
    assert len(messages) == 1
    assert 'импорт' in messages[0].lower()
