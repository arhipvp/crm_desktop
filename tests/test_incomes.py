from datetime import date

from services.client_service import add_client
from services.policy_service import add_policy
from services.payment_service import add_payment
from services.income_service import add_income, mark_incomes_deleted
from database.models import Income


def test_mark_incomes_deleted():
    client = add_client(name="BulkInc")
    policy = add_policy(
        client_id=client.id,
        policy_number="I1",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    payment = add_payment(policy_id=policy.id, amount=100, payment_date=date(2025, 1, 2))
    inc1 = add_income(payment_id=payment.id, amount=5)
    inc2 = add_income(payment_id=payment.id, amount=7)

    mark_incomes_deleted([inc1.id, inc2.id])

    assert Income.get_by_id(inc1.id).is_deleted is True
    assert Income.get_by_id(inc2.id).is_deleted is True
