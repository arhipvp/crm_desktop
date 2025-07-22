from datetime import date
from services.client_service import add_client
from services.policy_service import add_policy, update_policy
from database.models import Payment


def test_add_policy_first_payment_paid():
    c = add_client(name="C")
    pol = add_policy(
        client_id=c.id,
        policy_number="AAA",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        payments=[{"amount": 1000, "payment_date": date(2025, 1, 5)}],
        first_payment_paid=True,
    )
    pay = Payment.get(Payment.policy == pol)
    assert pay.actual_payment_date == pay.payment_date


def test_update_policy_first_payment_paid():
    c = add_client(name="U")
    pol = add_policy(
        client_id=c.id,
        policy_number="BBB",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        payments=[{"amount": 100, "payment_date": date(2025, 1, 10)}],
    )
    pay = Payment.get(Payment.policy == pol)
    assert pay.actual_payment_date is None
    update_policy(pol, first_payment_paid=True)
    pay = Payment.get_by_id(pay.id)
    assert pay.actual_payment_date == pay.payment_date
