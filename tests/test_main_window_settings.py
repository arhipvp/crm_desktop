import pytest
import logging

from PySide6.QtWidgets import QWidget, QTabWidget
import base64

from ui.main_window import MainWindow
from ui import settings as ui_settings

pytestmark = pytest.mark.slow


def test_main_window_restores_geometry_and_tab(tmp_path, monkeypatch, qapp):
    monkeypatch.setattr(ui_settings, "SETTINGS_PATH", tmp_path / "ui_settings.json")

    def dummy_init_tabs(self):
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        for i in range(6):
            self.tab_widget.addTab(QWidget(), str(i))

    monkeypatch.setattr(MainWindow, "init_tabs", dummy_init_tabs)
    monkeypatch.setattr(MainWindow, "on_tab_changed", lambda self, index: None)

    w1 = MainWindow()
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

    w2 = MainWindow()
    assert base64.b64encode(captured["geom"]).decode("ascii") == geom_saved
    assert w2.tab_widget.currentIndex() == tab_saved
    w2.close()
    qapp.processEvents()


def test_main_window_logs_on_invalid_geometry(tmp_path, monkeypatch, caplog, qapp):
    monkeypatch.setattr(ui_settings, "SETTINGS_PATH", tmp_path / "ui_settings.json")

    bad_geom = base64.b64encode(b"bad").decode("ascii")
    ui_settings.set_window_settings("MainWindow", {"geometry": bad_geom})

    def dummy_init_tabs(self):
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        for i in range(6):
            self.tab_widget.addTab(QWidget(), str(i))

    monkeypatch.setattr(MainWindow, "init_tabs", dummy_init_tabs)
    monkeypatch.setattr(MainWindow, "on_tab_changed", lambda self, index: None)

    def raise_error(self, ba):
        raise ValueError("broken")

    monkeypatch.setattr(MainWindow, "restoreGeometry", raise_error)

    with caplog.at_level(logging.ERROR):
        w = MainWindow()

    assert "Не удалось восстановить геометрию окна" in caplog.text
    w.close()
    qapp.processEvents()
