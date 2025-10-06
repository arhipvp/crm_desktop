from __future__ import annotations

from typing import Any, Iterable

import pytest
from PySide6.QtWidgets import QCheckBox, QMenu

from database.models import Executor
from ui.views.executor_table_view import ExecutorTableController, ExecutorTableView


class _DummySelect:
    def __init__(self, values: Iterable[Any]):
        self._values = list(values)

    def where(self, *_args, **_kwargs):
        return self

    def distinct(self):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def tuples(self):
        return [(value,) for value in self._values if value is not None]

    def limit(self, *_args, **_kwargs):
        return self

    def exists(self):
        return any(value is None for value in self._values)


class _DummyQuery:
    def __init__(self, values: Iterable[Any]):
        self._values = list(values)

    def select(self, *_args, **_kwargs):
        return _DummySelect(self._values)


@pytest.mark.usefixtures("ui_settings_temp_path")
def test_executor_filter_menu_includes_distinct_and_null(qapp, in_memory_db):
    visible = Executor.create(full_name="A-Visible", tg_id=111, is_active=True)
    hidden = Executor.create(full_name="Z-Hidden", tg_id=222, is_active=False)

    view = ExecutorTableView()
    view._on_per_page_changed(1)
    qapp.processEvents()

    assert view.model.rowCount() == 1
    assert view.model.get_item(0).full_name == visible.full_name

    controller: ExecutorTableController = view.controller  # type: ignore[assignment]
    controller._build_query_func = lambda **_filters: _DummyQuery(
        [None, visible.full_name, hidden.full_name]
    )

    menu = QMenu()
    try:
        view._create_choices_filter_widget(menu, 0, None)
        qapp.processEvents()

        actions = menu.actions()
        assert actions, "Меню фильтра должно содержать элементы"
        container = actions[0].defaultWidget()
        assert container is not None, "В меню отсутствует контейнер фильтра"

        checkboxes = container.findChildren(QCheckBox)
        assert checkboxes, "В меню ожидались чекбоксы"
        labels = {checkbox.text() for checkbox in checkboxes}

        assert "—" in labels, "Должно отображаться значение для NULL"
        assert (
            hidden.full_name in labels
        ), "Должно отображаться значение, отсутствующее на текущей странице"
    finally:
        menu.deleteLater()
        view.deleteLater()
