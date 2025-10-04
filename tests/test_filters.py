"""Тесты фильтрации в таблицах UI."""

from __future__ import annotations

from datetime import date

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QLabel, QLineEdit, QMenu, QPushButton

from database.models import Client, Deal, Payment, Policy
from ui import settings as ui_settings
from ui.base.base_table_view import BaseTableView
from ui.base.table_controller import TableController
from ui.common.multi_filter_proxy import ColumnFilterState
from ui.views.payment_table_view import PaymentTableView
from ui.views.deal_table_view import DealTableView
from ui.views import payment_table_view as payment_table_view_module
from ui.common.date_utils import get_date_or_none
from services.deals.dto import DealClientInfo, DealExecutorInfo, DealRowDTO
from services.deals.deal_table_controller import DealTableController


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
def test_choices_filter_adds_multi_value_state(
    qapp,
    in_memory_db,
    make_policy_with_payment,
):
    """Выбор нескольких элементов должен сохранять фильтр в column_filters."""

    ui_settings._CACHE = None

    _, _, _, payment1 = make_policy_with_payment(
        policy_kwargs={"policy_number": "CHO-001"},
        payment_kwargs={"amount": 10},
    )
    _, _, _, payment2 = make_policy_with_payment(
        policy_kwargs={"policy_number": "CHO-002"},
        payment_kwargs={"amount": 20},
    )

    view = BaseTableView(model_class=Payment)
    view.set_model_class_and_items(
        Payment,
        [payment1, payment2],
        total_count=2,
    )
    qapp.processEvents()

    assert view._settings_loaded is True

    labels = [
        payment1.policy.policy_number,
        payment2.policy.policy_number,
    ]
    payloads = [
        {"value": payment1.policy.id, "display": labels[0]},
        {"value": payment2.policy.id, "display": labels[1]},
    ]
    state = ColumnFilterState(
        "choices",
        payloads,
        display=", ".join(labels),
        meta={"choices_display": labels},
    )

    view._apply_column_filter(0, state, trigger_filter=False)

    stored = view._column_filters.get(0)
    assert stored is not None
    assert stored.type == "choices"
    assert stored.value == payloads
    assert view._column_filter_strings.get(0) == ", ".join(labels)

    view.deleteLater()


def test_choice_filter_without_value_serialization_and_controller():
    state = ColumnFilterState("choices", [{"value": None, "display": "Имя"}])

    assert state.backend_value() == ["Имя"]

    serialized = state.to_dict()
    assert serialized["value"] == ["Имя"]

    class DummyHeader:
        def visualIndex(self, logical: int) -> int:
            return logical

        def logicalIndex(self, visual: int) -> int:
            return visual

        def isSectionHidden(self, index: int) -> bool:
            return False

    class DummyTable:
        def __init__(self) -> None:
            self._header = DummyHeader()

        def horizontalHeader(self) -> DummyHeader:
            return self._header

    class DummyView:
        def __init__(self, filter_state: ColumnFilterState) -> None:
            self.COLUMN_FIELD_MAP = {0: "executor"}
            self._column_filters = {0: filter_state}
            self.table = DummyTable()
            self.page = 1
            self.per_page = 25
            self.controller = TableController(self)

        def is_checked(self, *_args, **_kwargs) -> bool:
            return False

        def get_search_text(self) -> str:
            return ""

        def get_date_filter(self):
            return None

        get_filters = BaseTableView.get_filters

    view = DummyView(state)
    filters = view.get_filters()

    assert filters["column_filters"] == {"executor": ["Имя"]}


@pytest.mark.usefixtures("ui_settings_temp_path")
def test_choices_filter_widget_has_search_and_filters(
    qapp,
    in_memory_db,
    make_policy_with_payment,
):
    """Виджет выбора значений содержит поле поиска и фильтрует список."""

    ui_settings._CACHE = None

    _, _, _, payment1 = make_policy_with_payment(
        policy_kwargs={"policy_number": "FLT-ONE"},
        payment_kwargs={"amount": 10},
    )
    _, _, _, payment2 = make_policy_with_payment(
        policy_kwargs={"policy_number": "FLT-TWO"},
        payment_kwargs={"amount": 20},
    )

    view = BaseTableView(model_class=Payment)
    view.set_model_class_and_items(
        Payment,
        [payment1, payment2],
        total_count=2,
    )
    qapp.processEvents()

    menu = QMenu()
    view._create_choices_filter_widget(menu, 0, None)
    qapp.processEvents()

    assert menu.actions(), "В меню должен появиться виджет фильтра"
    container = menu.actions()[0].defaultWidget()
    assert container is not None

    search_input = container.findChild(QLineEdit)
    assert search_input is not None, "Поле поиска не найдено"
    assert search_input.placeholderText() == "Поиск…"

    checkboxes = container.findChildren(QCheckBox)
    assert len(checkboxes) == 2
    checkbox_one = next((cb for cb in checkboxes if "FLT-ONE" in cb.text()), None)
    checkbox_two = next((cb for cb in checkboxes if "FLT-TWO" in cb.text()), None)
    assert checkbox_one is not None and checkbox_two is not None

    placeholder = None
    for label in container.findChildren(QLabel):
        if label.text() == "Нет значений":
            placeholder = label
            break
    assert placeholder is not None
    assert placeholder.isHidden()

    search_input.setText("one")
    qapp.processEvents()

    assert not checkbox_one.isHidden()
    assert checkbox_two.isHidden()

    select_all_btn = next(
        (btn for btn in container.findChildren(QPushButton) if btn.text() == "Выделить всё"),
        None,
    )
    clear_all_btn = next(
        (btn for btn in container.findChildren(QPushButton) if btn.text() == "Снять всё"),
        None,
    )
    assert select_all_btn is not None and clear_all_btn is not None

    checkbox_one.setChecked(False)
    checkbox_two.setChecked(False)
    qapp.processEvents()

    select_all_btn.click()
    qapp.processEvents()

    assert checkbox_one.isChecked()
    assert not checkbox_two.isChecked(), "Скрытый чекбокс не должен выделяться"

    search_input.clear()
    qapp.processEvents()

    checkbox_one.setChecked(True)
    checkbox_two.setChecked(True)
    qapp.processEvents()

    search_input.setText("one")
    qapp.processEvents()

    clear_all_btn.click()
    qapp.processEvents()

    assert not checkbox_one.isChecked()
    assert checkbox_two.isChecked(), "Скрытый чекбокс не должен сбрасываться"

    search_input.setText("zzz")
    qapp.processEvents()

    assert all(checkbox.isHidden() for checkbox in checkboxes)
    assert not placeholder.isHidden()

    search_input.clear()
    qapp.processEvents()

    assert all(not checkbox.isHidden() for checkbox in checkboxes)
    assert placeholder.isHidden()

    view.deleteLater()


@pytest.mark.usefixtures("ui_settings_temp_path")
def test_choices_filter_widget_completer_filters_values(
    qapp,
    in_memory_db,
    make_policy_with_payment,
):
    """Поле поиска предлагает существующие значения и фильтрует список."""

    ui_settings._CACHE = None

    _, _, _, payment1 = make_policy_with_payment(
        policy_kwargs={"policy_number": "CMP-ONE"},
        payment_kwargs={"amount": 50},
    )
    _, _, _, payment2 = make_policy_with_payment(
        policy_kwargs={"policy_number": "CMP-TWO"},
        payment_kwargs={"amount": 75},
    )

    view = BaseTableView(model_class=Payment)
    view.set_model_class_and_items(
        Payment,
        [payment1, payment2],
        total_count=2,
    )
    qapp.processEvents()

    menu = QMenu()
    view._create_choices_filter_widget(menu, 0, None)
    qapp.processEvents()

    container = menu.actions()[0].defaultWidget()
    assert container is not None

    search_input = container.findChild(QLineEdit)
    assert search_input is not None

    checkboxes = container.findChildren(QCheckBox)
    assert len(checkboxes) == 2
    expected_labels = sorted([cb.text() for cb in checkboxes], key=str.casefold)

    completer = search_input.completer()
    assert completer is not None
    model = completer.model()
    row_count = model.rowCount()
    suggestions = [
        model.data(model.index(row, 0), Qt.DisplayRole)
        for row in range(row_count)
    ]
    assert suggestions == expected_labels

    search_input.setText("cmp-one")
    qapp.processEvents()

    visible_checkboxes = [cb for cb in checkboxes if not cb.isHidden()]
    assert len(visible_checkboxes) == 1
    assert "CMP-ONE" in visible_checkboxes[0].text()

    search_input.clear()
    qapp.processEvents()

    assert all(not cb.isHidden() for cb in checkboxes)

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
    assert last_filters[Policy.policy_number] == ["PAY-001"]

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


def test_column_filter_state_backend_value_for_choices_single():
    state = ColumnFilterState(
        "choices",
        {"value": "alpha", "display": "Alpha"},
    )
    assert state.backend_value() == "alpha"


def test_column_filter_state_backend_value_for_choices_multiple():
    state = ColumnFilterState(
        "choices",
        [
            {"value": "one", "display": "One"},
            {"display": "Two"},
            3,
            None,
        ],
    )
    assert state.backend_value() == ["one", "Two", "3"]


@pytest.mark.usefixtures("ui_settings_temp_path")
def test_load_table_settings_restores_choices_filter(
    qapp,
    in_memory_db,
    make_policy_with_payment,
):
    """Фильтр со списком значений сохраняется и применяется после перезапуска."""

    ui_settings._CACHE = None

    _, _, _, payment1 = make_policy_with_payment(
        policy_kwargs={"policy_number": "RST-001"},
        payment_kwargs={"amount": 100},
    )
    _, _, _, payment2 = make_policy_with_payment(
        policy_kwargs={"policy_number": "RST-002"},
        payment_kwargs={"amount": 200},
    )
    _, _, _, payment3 = make_policy_with_payment(
        policy_kwargs={"policy_number": "RST-003"},
        payment_kwargs={"amount": 300},
    )

    payments = [payment1, payment2, payment3]

    view = BaseTableView(model_class=Payment)
    view.set_model_class_and_items(Payment, payments, total_count=3)
    qapp.processEvents()

    assert view._settings_loaded is True

    labels = [payment1.policy.policy_number, payment2.policy.policy_number]
    payloads = [
        {"value": payment1.policy.id, "display": labels[0]},
        {"value": payment2.policy.id, "display": labels[1]},
    ]
    state = ColumnFilterState(
        "choices",
        payloads,
        display=", ".join(labels),
        meta={"choices_display": labels},
    )

    view._apply_column_filter(0, state, trigger_filter=False)
    qapp.processEvents()

    saved_settings = ui_settings.get_table_settings(view.settings_id)
    assert saved_settings.get("column_filters")
    assert str(0) in saved_settings["column_filters"]

    view.deleteLater()

    new_view = BaseTableView(model_class=Payment)
    new_view.set_model_class_and_items(Payment, payments, total_count=3)
    qapp.processEvents()

    restored = new_view._column_filters.get(0)
    assert restored is not None
    assert restored.type == "choices"
    assert restored.value == payloads

    qapp.processEvents()

    assert new_view.proxy.rowCount() == 2
    visible_policies = {
        new_view.model.objects[  # type: ignore[attr-defined]
            new_view.proxy.mapToSource(new_view.proxy.index(row, 0)).row()
        ].policy.policy_number
        for row in range(new_view.proxy.rowCount())
    }
    assert visible_policies == set(labels)

    new_view.deleteLater()


@pytest.mark.usefixtures("ui_settings_temp_path")
def test_deal_table_show_deleted_filter(qapp, in_memory_db):
    """Чекбокс «Показывать удалённые» добавляет записи в выборку."""

    ui_settings._CACHE = None

    client = Client.create(name="Client")
    Deal.create(client=client, description="Active", start_date=date.today())
    Deal.create(
        client=client,
        description="Deleted",
        start_date=date.today(),
        is_deleted=True,
    )
    Deal.create(
        client=client,
        description="ClosedDeleted",
        start_date=date.today(),
        is_deleted=True,
        is_closed=True,
    )

    view = DealTableView()
    qapp.processEvents()

    descriptions = {deal.description for deal in view.model.objects}
    assert "Deleted" not in descriptions
    assert "ClosedDeleted" not in descriptions
    assert all(not deal.is_deleted for deal in view.model.objects)

    show_deleted_box = view.checkboxes["Показывать удалённые"]
    show_deleted_box.setChecked(True)
    qapp.processEvents()

    filters = view.get_filters()
    assert filters["show_deleted"] is True

    descriptions = {deal.description for deal in view.model.objects}
    assert {"Active", "Deleted", "ClosedDeleted"} <= descriptions
    assert any(deal.is_deleted for deal in view.model.objects)


@pytest.mark.usefixtures("ui_settings_temp_path")
def test_deal_table_multi_choice_filters(qapp, monkeypatch):
    """Фильтр по статусам и исполнителям оставляет только выбранные сделки."""

    ui_settings._CACHE = None

    today = date.today()
    client_info = DealClientInfo(id=1, name="Client")
    exec1 = DealExecutorInfo(id=1, full_name="Executor A")
    exec2 = DealExecutorInfo(id=2, full_name="Executor B")
    exec3 = DealExecutorInfo(id=3, full_name="Executor C")

    deals = [
        DealRowDTO(
            id=1,
            reminder_date=None,
            client=client_info,
            status="NEW",
            description="Alpha",
            calculations=None,
            start_date=today,
            is_closed=False,
            closed_reason=None,
            drive_folder_path=None,
            drive_folder_link=None,
            is_deleted=False,
            executor=exec1,
        ),
        DealRowDTO(
            id=2,
            reminder_date=None,
            client=client_info,
            status="SUCCESS",
            description="Beta",
            calculations=None,
            start_date=today,
            is_closed=False,
            closed_reason=None,
            drive_folder_path=None,
            drive_folder_link=None,
            is_deleted=False,
            executor=exec2,
        ),
        DealRowDTO(
            id=3,
            reminder_date=None,
            client=client_info,
            status="FAILED",
            description="Gamma",
            calculations=None,
            start_date=today,
            is_closed=False,
            closed_reason=None,
            drive_folder_path=None,
            drive_folder_link=None,
            is_deleted=False,
            executor=exec3,
        ),
    ]

    def fake_load_data(self):
        self._apply_items(deals, total_count=len(deals))

    monkeypatch.setattr(DealTableController, "load_data", fake_load_data)

    view = DealTableView()
    qapp.processEvents()

    assert view.model is not None

    view.on_filter_changed = lambda *a, **k: None  # избегаем перезагрузки данных

    status_col = view.get_column_index("status")
    executor_col = view.get_column_index("executor")

    status_labels = ["NEW", "SUCCESS"]
    status_payloads = [
        {"value": "NEW", "display": "NEW"},
        {"value": "SUCCESS", "display": "SUCCESS"},
    ]
    executor_labels = ["Executor A", "Executor B"]
    executor_payloads = [
        {"value": None, "display": "Executor A"},
        {"value": None, "display": "Executor B"},
    ]

    view._apply_column_filter(
        status_col,
        ColumnFilterState(
            "choices",
            status_payloads,
            display=", ".join(status_labels),
            meta={"choices_display": status_labels},
        ),
        trigger_filter=False,
    )

    view._apply_column_filter(
        executor_col,
        ColumnFilterState(
            "choices",
            executor_payloads,
            display=", ".join(executor_labels),
            meta={"choices_display": executor_labels},
        ),
        trigger_filter=False,
    )

    qapp.processEvents()

    assert view.proxy.rowCount() == 2

    description_col = view.get_column_index("description")
    remaining = {
        view.proxy.data(view.proxy.index(row, description_col), Qt.DisplayRole)
        for row in range(view.proxy.rowCount())
    }
    assert remaining == {"Alpha", "Beta"}

    view.deleteLater()
