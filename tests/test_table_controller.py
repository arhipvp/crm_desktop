import types
from unittest.mock import MagicMock

from ui.base.table_controller import TableController
from ui import settings as ui_settings


def test_on_reset_filters(monkeypatch):
    header = types.SimpleNamespace(set_all_filters=MagicMock())
    table = types.SimpleNamespace(horizontalHeader=lambda: header)
    view = types.SimpleNamespace(
        clear_filters=MagicMock(),
        save_table_settings=MagicMock(),
        table=table,
    )
    controller = TableController(view)
    controller.on_filter_changed = MagicMock()

    monkeypatch.setattr(ui_settings, "set_table_filters", MagicMock())

    controller._on_reset_filters()

    view.clear_filters.assert_called_once()
    view.save_table_settings.assert_called_once()
    controller.on_filter_changed.assert_called_once()
    ui_settings.set_table_filters.assert_not_called()
