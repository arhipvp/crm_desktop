import datetime
import pytest
from peewee import SqliteDatabase

from database.db import db
from database.models import Client, Policy, Payment
from services import payment_service as pay_svc
from services import policy_service as policy_svc


@pytest.fixture()
def setup_db(monkeypatch):
    test_db = SqliteDatabase(':memory:')
    db.initialize(test_db)
    test_db.create_tables([Client, Policy, Payment])
    monkeypatch.setattr(
        pay_svc,
        "add_payment",
        lambda **kw: Payment.create(
            policy=kw["policy"],
            amount=kw["amount"],
            payment_date=kw["payment_date"],
        ),
    )
    yield
    test_db.drop_tables([Client, Policy, Payment])
    test_db.close()


def test_merge_policy_payments_adds_missing(setup_db):
    client = Client.create(name="C")
    d1 = datetime.date(2024, 1, 1)
    d2 = datetime.date(2024, 2, 1)
    policy = Policy.create(client=client, policy_number="P", start_date=d1, end_date=d2)
    Payment.create(policy=policy, amount=100, payment_date=d1)

    pay_svc.merge_policy_payments(
        policy,
        [
            {"amount": 100, "payment_date": d1},
            {"amount": 200, "payment_date": d2},
        ],
    )

    payments = list(policy.payments)
    assert len(payments) == 2
    assert {(p.payment_date, p.amount) for p in payments} == {
        (d1, 100),
        (d2, 200),
    }


def test_update_policy_adds_payments_and_marks_first_paid(setup_db):
    client = Client.create(name="C")
    d1 = datetime.date(2024, 1, 1)
    d2 = datetime.date(2024, 2, 1)
    d3 = datetime.date(2024, 3, 1)
    policy = Policy.create(
        client=client,
        policy_number="P",
        start_date=d1,
        end_date=d3,
    )
    Payment.create(policy=policy, amount=100, payment_date=d1)

    policy_svc.update_policy(
        policy,
        payments=[{"amount": 200, "payment_date": d2}],
        first_payment_paid=True,
    )

    payments = list(policy.payments.order_by(Payment.payment_date))
    assert len(payments) == 2
    assert payments[0].actual_payment_date == payments[0].payment_date
    assert payments[1].amount == 200 and payments[1].payment_date == d2
