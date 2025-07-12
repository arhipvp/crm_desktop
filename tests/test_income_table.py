from datetime import date
from PySide6.QtCore import Qt

from services.client_service import add_client
from services.policy_service import add_policy
from services.payment_service import add_payment
from services.income_service import add_income
from ui.views.income_table_view import IncomeTableModel
from database.models import Income


def test_income_table_shows_payment_date():
    client = add_client(name="X")
    policy = add_policy(
        client_id=client.id,
        policy_number="P1",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    payment = add_payment(policy_id=policy.id, amount=10, payment_date=date(2025, 1, 2))
    income = add_income(payment_id=payment.id, amount=5, received_date=date(2025, 1, 3))

    model = IncomeTableModel([income], Income)

    # Проверка на наличие "Дата платежа"
    assert "Дата платежа" in model.headers
    idx = model.index(0, model.headers.index("Дата платежа"))
    assert model.data(idx, Qt.DisplayRole) == "02.01.2025"

    # Проверка на наличие "Дата начала"
    assert "Дата начала" in model.headers
    start_idx = model.index(0, model.headers.index("Дата начала"))
    assert model.data(start_idx, Qt.DisplayRole) == "01.01.2025"

    # Проверка на наличие колонки "Сделка"
    assert "Сделка" in model.headers
    deal_idx = model.index(0, model.headers.index("Сделка"))
    assert model.data(deal_idx, Qt.DisplayRole) == "—"
