"""Тесты фильтрации в таблицах UI."""

from __future__ import annotations

from datetime import date

import pytest
from PySide6.QtCore import Qt

from database.models import Payment, Policy
from ui import settings as ui_settings
from ui.base.base_table_view import BaseTableView
from ui.common.multi_filter_proxy import ColumnFilterState
from ui.views.payment_table_view import PaymentTableView
from ui.views import payment_table_view as payment_table_view_module
from ui.common.date_utils import get_date_or_none


@pytest.mark.usefixtures("ui_settings_temp_path")
def test_header_filter_input_filters_proxy(
    qapp,
    in_memory_db,
    make_policy_with_payment,
):
    """Значение фильтра в заголовке должно сужать данные в таблице."""

    ui_settings._CACHE = None  # сброс кеша настроек

    _, _, _, payment1 = make_policy_with_payment(
        policy_kwargs={"policy_number": "POL-001"},
        payment_kwargs={"amount": 100},
    )
    _, _, _, payment2 = make_policy_with_payment(
        policy_kwargs={"policy_number": "POL-002"},
        payment_kwargs={"amount": 200},
    )

    view = BaseTableView(model_class=Payment)
    view.set_model_class_and_items(Payment, [payment1, payment2], total_count=2)
    qapp.processEvents()

    assert view.proxy.rowCount() == 2

    view._on_filter_text_changed(0, "POL-001")
    qapp.processEvents()

    assert view.proxy.rowCount() == 1
    index = view.proxy.index(0, 0)
    display_text = view.proxy.data(index, Qt.DisplayRole)
    assert "POL-001" in display_text
    state = view._column_filters[0]
    assert isinstance(state, ColumnFilterState)
    assert state.type == "text"
    assert state.value == "POL-001"
    view.deleteLater()


@pytest.mark.usefixtures("ui_settings_temp_path")
def test_column_filter_passed_to_payment_service(
    qapp,
    in_memory_db,
    make_policy_with_payment,
    monkeypatch,
):
    """Фильтр из заголовка передаётся в сервис и попадает в SQL."""

    ui_settings._CACHE = None  # сброс кеша настроек

    make_policy_with_payment(
        policy_kwargs={"policy_number": "PAY-001"},
        payment_kwargs={"amount": 150},
    )
    make_policy_with_payment(
        policy_kwargs={"policy_number": "PAY-002"},
        payment_kwargs={"amount": 250},
    )

    captured_column_filters: list[dict | None] = []
    captured_sql: list[tuple[str, list | tuple]] = []

    original_get_page = payment_table_view_module.get_payments_page
    original_build_query = payment_table_view_module.build_payment_query

    def spy_get_payments_page(page, per_page, **kwargs):
        captured_column_filters.append(kwargs.get("column_filters"))
        return original_get_page(page, per_page, **kwargs)

    def spy_build_payment_query(*args, **kwargs):
        query = original_build_query(*args, **kwargs)
        captured_sql.append(query.sql())
        return query

    monkeypatch.setattr(
        payment_table_view_module,
        "get_payments_page",
        spy_get_payments_page,
    )
    monkeypatch.setattr(
        payment_table_view_module,
        "build_payment_query",
        spy_build_payment_query,
    )

    view = PaymentTableView()
    qapp.processEvents()

    view._on_filter_text_changed(0, "PAY-001")
    qapp.processEvents()

    assert captured_column_filters, "Сервис не получил фильтры"
    last_filters = captured_column_filters[-1]
    assert Policy.policy_number in last_filters
    assert last_filters[Policy.policy_number] == "PAY-001"

    assert captured_sql, "SQL-запрос не сформирован"
    sql, params = captured_sql[-1]
    assert "policy_number\" AS TEXT) LIKE ?" in sql
    assert any("PAY-001" in str(param) for param in params)

    view.deleteLater()


@pytest.mark.usefixtures("ui_settings_temp_path")
def test_date_filter_resets_to_minimum(qapp):
    """Диапазон дат не сохраняется после очистки фильтров."""

    ui_settings._CACHE = None

    view = BaseTableView(model_class=Payment, date_filter_field="created_at")
    qapp.processEvents()

    min_date_q = view.date_from.minimumDate()
    assert min_date_q == view.date_to.minimumDate()
    assert min_date_q.toPython() == date(2000, 1, 1)

    # По умолчанию фильтр пустой
    assert view.get_date_filter() is None
    assert get_date_or_none(view.date_from) is None

    later_start = min_date_q.addDays(5)
    later_end = min_date_q.addDays(10)
    view.date_from.setDate(later_start)
    view.date_to.setDate(later_end)
    qapp.processEvents()

    date_filter = view.get_date_filter()
    assert date_filter is not None
    rng = date_filter["created_at"]
    assert rng == (later_start.toPython(), later_end.toPython())

    view.clear_filters()
    qapp.processEvents()

    assert view.get_date_filter() is None
    assert get_date_or_none(view.date_from) is None

    view.deleteLater()
