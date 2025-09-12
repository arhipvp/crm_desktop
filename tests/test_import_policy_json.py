from PySide6.QtWidgets import QApplication, QDialog, QTabWidget

from ui.main_window import MainWindow


def _create_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _prepare_main_window(monkeypatch):
    """Создаёт MainWindow без загрузки реальных вкладок."""

    def dummy_init_tabs(self):
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

    monkeypatch.setattr(MainWindow, "init_tabs", dummy_init_tabs)
    monkeypatch.setattr(MainWindow, "on_tab_changed", lambda self, index: None)

    return MainWindow()


def test_open_import_policy_json_shows_message_once(monkeypatch):
    _create_app()

    created = []

    class DummyDlg:
        def __init__(self, parent=None):
            created.append(1)

        def exec(self):
            return QDialog.Accepted

    monkeypatch.setattr("ui.main_window.ImportPolicyJsonForm", DummyDlg)

    mw = _prepare_main_window(monkeypatch)
    messages = []
    monkeypatch.setattr(
        mw.status_bar, "showMessage", lambda msg, timeout=0: messages.append(msg)
    )

    mw.open_import_policy_json()

    assert len(created) == 1
    assert len(messages) == 1
    assert "импорт" in messages[0].lower()


def test_open_import_policy_json_cancel_shows_no_message(monkeypatch):
    _create_app()

    class DummyDlg:
        def __init__(self, parent=None):
            pass

        def exec(self):
            return QDialog.Rejected

    monkeypatch.setattr("ui.main_window.ImportPolicyJsonForm", DummyDlg)

    mw = _prepare_main_window(monkeypatch)
    messages = []
    monkeypatch.setattr(
        mw.status_bar, "showMessage", lambda msg, timeout=0: messages.append(msg)
    )

    mw.open_import_policy_json()

    assert messages == []

