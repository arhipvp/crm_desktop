from datetime import date
from PySide6.QtCore import Qt

from services.client_service import add_client
from services.policy_service import add_policy
from services.payment_service import add_payment
from services.expense_service import add_expense
from ui.views.expense_table_view import ExpenseTableModel
from database.models import Expense


def test_expense_table_shows_payment_info():
    client = add_client(name="X")
    policy = add_policy(
        client_id=client.id,
        policy_number="P1",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    payment = add_payment(policy_id=policy.id, amount=10, payment_date=date(2025, 1, 2))
    expense = add_expense(
        payment_id=payment.id,
        amount=5,
        expense_type="agent",
        expense_date=date(2025, 1, 3),
    )

    model = ExpenseTableModel([expense], Expense)

    expected_headers = [
        "Полис",
        "Сделка",
        "Клиент",
        "Дата начала",
        "Тип расхода",
        "Сумма платежа",
        "Дата платежа",
        "Сумма расхода",
        "Дата выплаты",
    ]
    for header in expected_headers:
        assert header in model.headers, f"Ожидается заголовок '{header}'"

    start_idx = model.index(0, model.headers.index("Дата начала"))
    assert model.data(start_idx, Qt.DisplayRole) == "01.01.2025"

    pay_date_idx = model.index(0, model.headers.index("Дата платежа"))
    assert model.data(pay_date_idx, Qt.DisplayRole) == "02.01.2025"

    pay_sum_idx = model.index(0, model.headers.index("Сумма платежа"))
    assert model.data(pay_sum_idx, Qt.DisplayRole) == "10.00 ₽"

    amount_idx = model.index(0, model.headers.index("Сумма расхода"))
    assert model.data(amount_idx, Qt.DisplayRole) == "5.00 ₽"

    expense_date_idx = model.index(0, model.headers.index("Дата выплаты"))
    assert model.data(expense_date_idx, Qt.DisplayRole) == "03.01.2025"

    type_idx = model.index(0, model.headers.index("Тип расхода"))
    assert model.data(type_idx, Qt.DisplayRole) == "agent"
