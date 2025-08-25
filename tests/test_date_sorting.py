import datetime
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from database.models import Client, Policy, Payment
from ui.base.base_table_view import BaseTableView


def _create_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_date_sorting_with_filter(in_memory_db):
    _create_app()
    client = Client.create(name="C")
    policy1 = Policy.create(client=client, deal=None, policy_number="P1", start_date=datetime.date.today())
    policy2 = Policy.create(client=client, deal=None, policy_number="P2", start_date=datetime.date.today())
    pay1 = Payment.create(policy=policy1, amount=100, payment_date=datetime.date(2023, 12, 10))
    pay2 = Payment.create(policy=policy2, amount=100, payment_date=datetime.date(2024, 1, 2))

    view = BaseTableView(model_class=Payment)
    view.set_model_class_and_items(Payment, [pay1, pay2], total_count=2)

    # активируем фильтр, чтобы прокси-модель применяла сортировку при фильтрации
    view.proxy_model.setFilterFixedString("P")

    column = view.get_column_index("payment_date")
    view.table.sortByColumn(column, Qt.AscendingOrder)
    QApplication.processEvents()

    idx0 = view.proxy_model.index(0, column)
    idx1 = view.proxy_model.index(1, column)
    first_date = view.proxy_model.data(idx0, Qt.DisplayRole)
    second_date = view.proxy_model.data(idx1, Qt.DisplayRole)

    assert first_date == "10.12.2023"
    assert second_date == "02.01.2024"
