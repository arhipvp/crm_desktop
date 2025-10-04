import types
from unittest.mock import MagicMock

from ui.base.table_controller import TableController
from ui.common.multi_filter_proxy import ColumnFilterState
from ui import settings as ui_settings


def test_on_reset_filters(monkeypatch):
    header = types.SimpleNamespace(set_all_filters=MagicMock())
    view = types.SimpleNamespace(
        clear_filters=MagicMock(),
        save_table_settings=MagicMock(),
        table=types.SimpleNamespace(horizontalHeader=lambda: header),
    )
    controller = TableController(view)
    controller.on_filter_changed = MagicMock()

    monkeypatch.setattr(ui_settings, "set_table_filters", MagicMock())

    controller._on_reset_filters()

    view.clear_filters.assert_called_once()
    view.save_table_settings.assert_called_once()
    controller.on_filter_changed.assert_called_once()
    ui_settings.set_table_filters.assert_not_called()


class _DummyHeader:
    def visualIndex(self, logical: int) -> int:
        return logical

    def logicalIndex(self, visual: int) -> int:
        return visual

    def isSectionHidden(self, index: int) -> bool:
        return False


class _DummyTable:
    def __init__(self) -> None:
        self._header = _DummyHeader()

    def horizontalHeader(self) -> _DummyHeader:
        return self._header


class _DummyView:
    def __init__(self, state: ColumnFilterState) -> None:
        self._column_filters = {0: state}
        self.table = _DummyTable()
        self.COLUMN_FIELD_MAP = {0: "executor"}

    def is_checked(self, *_args, **_kwargs) -> bool:
        return False

    def get_search_text(self) -> str:
        return ""

    def get_date_filter(self):
        return None


def test_get_filters_normalizes_display_only_choice():
    state = ColumnFilterState("choices", [{"value": None, "display": "Имя"}])
    view = _DummyView(state)
    controller = TableController(view)

    filters = controller.get_filters()

    assert filters["column_filters"] == {"executor": ["Имя"]}
