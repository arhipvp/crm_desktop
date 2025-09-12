import pytest
import logging

from PySide6.QtWidgets import QWidget, QDialog
import base64

from ui.main_window import MainWindow
from ui import settings as ui_settings

pytestmark = pytest.mark.slow


def test_main_window_restores_geometry_and_tab(ui_settings_temp_path, monkeypatch, qapp, dummy_main_window):

    w1 = dummy_main_window(tab_count=6)
    w1.show()
    qapp.processEvents()
    w1.resize(900, 700)
    target_index = 3
    w1.tab_widget.setCurrentIndex(target_index)
    qapp.processEvents()
    w1.close()
    qapp.processEvents()

    settings = ui_settings.get_window_settings("MainWindow")
    geom_saved = settings["geometry"]
    tab_saved = settings["last_tab"]

    captured = {}

    def fake_restore(self, ba):
        captured["geom"] = bytes(ba)
        return True

    monkeypatch.setattr(MainWindow, "restoreGeometry", fake_restore)

    w2 = dummy_main_window(tab_count=6)
    assert base64.b64encode(captured["geom"]).decode("ascii") == geom_saved
    assert w2.tab_widget.currentIndex() == tab_saved
    w2.close()
    qapp.processEvents()


def test_main_window_logs_on_invalid_geometry(ui_settings_temp_path, monkeypatch, caplog, qapp, dummy_main_window):

    bad_geom = base64.b64encode(b"bad").decode("ascii")
    ui_settings.set_window_settings("MainWindow", {"geometry": bad_geom})

    def raise_error(self, ba):
        raise ValueError("broken")

    monkeypatch.setattr(MainWindow, "restoreGeometry", raise_error)

    with caplog.at_level(logging.ERROR):
        w = dummy_main_window(tab_count=6)

    assert "Не удалось восстановить геометрию окна" in caplog.text
    w.close()
    qapp.processEvents()


@pytest.mark.parametrize(
    "exec_result, expected_messages",
    [
        (QDialog.Accepted, 1),
        (QDialog.Rejected, 0),
    ],
)
def test_open_import_policy_json_message(
    monkeypatch, dummy_main_window, exec_result, expected_messages
):
    created = []

    class DummyDlg:
        def __init__(self, parent=None):
            created.append(1)

        def exec(self):
            return exec_result

    monkeypatch.setattr("ui.main_window.ImportPolicyJsonForm", DummyDlg)

    mw = dummy_main_window()
    messages = []
    monkeypatch.setattr(
        mw.status_bar, "showMessage", lambda msg, timeout=0: messages.append(msg)
    )

    mw.open_import_policy_json()

    assert len(created) == 1
    assert len(messages) == expected_messages
    if expected_messages:
        assert "импорт" in messages[0].lower()
