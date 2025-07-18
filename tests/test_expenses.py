from datetime import date

from services.client_service import add_client
from services.policy_service import add_policy
from services.payment_service import add_payment
from services.expense_service import add_expense, mark_expenses_deleted
from database.models import Expense


def test_mark_expenses_deleted():
    client = add_client(name="BulkExp")
    policy = add_policy(
        client_id=client.id,
        policy_number="E1",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    payment = add_payment(policy_id=policy.id, amount=100, payment_date=date(2025, 1, 2))
    exp1 = add_expense(payment_id=payment.id, amount=5, expense_type="agent")
    exp2 = add_expense(payment_id=payment.id, amount=7, expense_type="agent")

    mark_expenses_deleted([exp1.id, exp2.id])

    assert Expense.get_by_id(exp1.id).is_deleted is True
    assert Expense.get_by_id(exp2.id).is_deleted is True
