from datetime import date
from PySide6.QtCore import Qt

from services.client_service import add_client
from services.policy_service import add_policy, attach_premium
from services.payment_service import add_payment
from ui.views.policy_table_view import PolicyTableModel
from database.models import Policy


def test_policy_table_premium_column():
    client = add_client(name="C")
    policy = add_policy(
        client_id=client.id,
        policy_number="P1",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    add_payment(policy_id=policy.id, amount=100, payment_date=date(2025, 1, 2))
    add_payment(policy_id=policy.id, amount=200, payment_date=date(2025, 2, 2))

    items = [policy]
    attach_premium(items)
    model = PolicyTableModel(items, Policy)
    assert model.headers[-1] == "Страховая премия"
    idx = model.index(0, model.columnCount() - 1)
    assert model.data(idx, Qt.DisplayRole) == "300,00 ₽"
