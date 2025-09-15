import datetime
import pytest
from PySide6.QtCore import Qt

from database.models import Client, Policy, Payment
from ui.base.base_table_view import BaseTableView
from ui.views.policy_table_view import PolicyTableView
from PySide6.QtWidgets import QHeaderView


@pytest.mark.parametrize("view_class", [BaseTableView, PolicyTableView])
@pytest.mark.parametrize("sort_order", [Qt.AscendingOrder, Qt.DescendingOrder])
def test_table_sorting(view_class, sort_order, in_memory_db, qapp, monkeypatch):
    client = Client.create(name="C")
    today = datetime.date.today()

    if view_class is BaseTableView:
        policy1 = Policy.create(
            client=client, deal=None, policy_number="P1", start_date=today
        )
        policy2 = Policy.create(
            client=client, deal=None, policy_number="P2", start_date=today
        )
        pay1 = Payment.create(
            policy=policy1, amount=100, payment_date=datetime.date(2023, 12, 10)
        )
        pay2 = Payment.create(
            policy=policy2, amount=100, payment_date=datetime.date(2024, 1, 2)
        )

        view = BaseTableView(model_class=Payment)
        view.set_model_class_and_items(Payment, [pay1, pay2], total_count=2)
        # активируем фильтр, чтобы прокси-модель применяла сортировку при фильтрации
        view.proxy.set_filter(0, "P")
        column = view.get_column_index("payment_date")
    else:
        p1 = Policy.create(
            client=client, deal=None, policy_number="P1", start_date=today
        )
        p2 = Policy.create(
            client=client, deal=None, policy_number="P2", start_date=today
        )

        def fake_load_data(self):
            self.set_model_class_and_items(Policy, [p1, p2], total_count=2)

        monkeypatch.setattr(PolicyTableView, "load_data", fake_load_data)
        view = view_class()
        view.load_data()
        column = 2  # столбец номера полиса

    header = view.table.horizontalHeader()
    assert isinstance(header, QHeaderView)
    view.table.sortByColumn(column, sort_order)
    qapp.processEvents()

    assert view.current_sort_column == column
    assert view.current_sort_order == sort_order

    if view_class is BaseTableView:
        idx0 = view.proxy.index(0, column)
        idx1 = view.proxy.index(1, column)
        first_date = view.proxy.data(idx0, Qt.DisplayRole)
        second_date = view.proxy.data(idx1, Qt.DisplayRole)
        if sort_order == Qt.AscendingOrder:
            assert first_date == "10.12.2023"
            assert second_date == "02.01.2024"
        else:
            assert first_date == "02.01.2024"
            assert second_date == "10.12.2023"

    view.refresh()
    qapp.processEvents()
    header = view.table.horizontalHeader()
    assert header.sortIndicatorSection() == column
    assert header.sortIndicatorOrder() == sort_order
