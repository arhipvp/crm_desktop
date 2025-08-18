import pytest

from PySide6.QtWidgets import QApplication, QWidget, QTabWidget
import base64

from ui.main_window import MainWindow
from ui import settings as ui_settings

pytestmark = pytest.mark.slow


def _create_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_main_window_restores_geometry_and_tab(tmp_path, monkeypatch):
    _create_app()
    monkeypatch.setattr(ui_settings, "SETTINGS_PATH", tmp_path / "ui_settings.json")

    def dummy_init_tabs(self):
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        for i in range(6):
            self.tab_widget.addTab(QWidget(), str(i))

    monkeypatch.setattr(MainWindow, "init_tabs", dummy_init_tabs)
    monkeypatch.setattr(MainWindow, "on_tab_changed", lambda self, index: None)

    app = QApplication.instance()
    w1 = MainWindow()
    w1.show()
    app.processEvents()
    w1.resize(900, 700)
    target_index = 3
    w1.tab_widget.setCurrentIndex(target_index)
    app.processEvents()
    w1.close()
    app.processEvents()

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
    app.processEvents()
