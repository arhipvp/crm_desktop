from datetime import date

from services.client_service import add_client
from services.policy_service import add_policy
from services.payment_service import add_payment, mark_payments_paid
from database.models import Income, Payment


def test_add_payment_creates_income():
    client = add_client(name="Покупатель")
    policy = add_policy(
        client_id=client.id,
        policy_number="PAY123",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )

    payment = add_payment(
        policy_id=policy.id, amount=5000, payment_date=date(2025, 2, 1)
    )

    assert payment.id is not None
    income = Income.get_or_none(Income.payment == payment)
    assert income is not None
    # Доход создаётся автоматически, но сумма должна быть нулевой
    assert income.amount == 0


def test_mark_payments_paid():
    client = add_client(name="Bulk")
    policy = add_policy(
        client_id=client.id,
        policy_number="B1",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    p1 = add_payment(policy_id=policy.id, amount=100, payment_date=date(2025, 1, 2))
    p2 = add_payment(policy_id=policy.id, amount=150, payment_date=date(2025, 1, 3))
    mark_payments_paid([p1.id, p2.id])
    paid_dt = date(1900, 1, 2)
    assert Payment.get_by_id(p1.id).actual_payment_date == paid_dt
    assert Payment.get_by_id(p2.id).actual_payment_date == paid_dt
