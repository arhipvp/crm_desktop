import types
from unittest.mock import MagicMock

from ui.base.table_controller import TableController
from ui import settings as ui_settings


def test_on_reset_filters(monkeypatch):
    filter_controls = types.SimpleNamespace(clear_all=MagicMock())
    view = types.SimpleNamespace(
        filter_controls=filter_controls,
        save_table_settings=MagicMock(),
        clear_header_filters=MagicMock(),
    )
    controller = TableController(view)
    controller.on_filter_changed = MagicMock()

    monkeypatch.setattr(ui_settings, "set_table_filters", MagicMock())

    controller._on_reset_filters()

    filter_controls.clear_all.assert_called_once()
    view.save_table_settings.assert_called_once()
    view.clear_header_filters.assert_called_once()
    controller.on_filter_changed.assert_called_once()
    ui_settings.set_table_filters.assert_not_called()
