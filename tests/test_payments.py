from datetime import date

from services.client_service import add_client
from services.policy_service import add_policy
from services.payment_service import add_payment
from database.models import Payment, Income


def test_add_payment_creates_income():
    client = add_client(name="Покупатель")
    policy = add_policy(
        client_id=client.id,
        policy_number="PAY123",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )

    payment = add_payment(policy_id=policy.id, amount=5000, payment_date=date(2025, 2, 1))

    assert payment.id is not None
    income = Income.get_or_none(Income.payment == payment)
    assert income is not None
    assert income.amount == 5000

