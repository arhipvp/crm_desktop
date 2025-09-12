import datetime

from PySide6.QtCore import Qt

from database.models import Client, Policy
from ui.views.policy_table_view import PolicyTableView


class DummyPolicyTableView(PolicyTableView):
    """Полностью отключает загрузку данных в конструкторе."""

    def load_data(self):  # pragma: no cover - простая заглушка
        pass


def test_policy_table_sort_preserved_after_refresh(in_memory_db, qapp):

    client = Client.create(name="C")
    today = datetime.date.today()
    p1 = Policy.create(client=client, deal=None, policy_number="P1", start_date=today)
    p2 = Policy.create(client=client, deal=None, policy_number="P2", start_date=today)

    view = DummyPolicyTableView()
    view.load_data = lambda: view.set_model_class_and_items(Policy, [p1, p2], total_count=2)
    view.load_data()

    column = 2  # столбец номера полиса
    view.table.sortByColumn(column, Qt.DescendingOrder)
    qapp.processEvents()

    assert view.current_sort_column == column
    assert view.current_sort_order == Qt.DescendingOrder

    # имитируем обновление данных после создания сделки
    view.refresh()
    qapp.processEvents()

    header = view.table.horizontalHeader()
    assert header.sortIndicatorSection() == column
    assert header.sortIndicatorOrder() == Qt.DescendingOrder

