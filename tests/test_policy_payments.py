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


def test_sync_policy_payments_adds_and_removes(setup_db):
    client = Client.create(name="C")
    d1 = datetime.date(2024, 1, 1)
    d2 = datetime.date(2024, 2, 1)
    d3 = datetime.date(2024, 3, 1)
    policy = Policy.create(client=client, policy_number="P", start_date=d1, end_date=d3)
    p1 = Payment.create(policy=policy, amount=100, payment_date=d1)
    p2 = Payment.create(policy=policy, amount=200, payment_date=d2)

    pay_svc.sync_policy_payments(
        policy,
        [
            {"amount": 100, "payment_date": d1},  # остаётся
            {"amount": 300, "payment_date": d3},  # новый
        ],
    )

    payments = list(policy.payments)
    assert {(p.payment_date, p.amount) for p in payments} == {
        (d1, 100),
        (d3, 300),
    }
    # Проверяем, что второй платеж удалён
    assert Payment.select().where(Payment.id == p2.id).count() == 0


def test_update_policy_syncs_payments_and_marks_first_paid(setup_db):
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
    Payment.create(policy=policy, amount=200, payment_date=d2)

    policy_svc.update_policy(
        policy,
        payments=[
            {"amount": 200, "payment_date": d2},  # остаётся
            {"amount": 300, "payment_date": d3},  # новый
        ],
        first_payment_paid=True,
    )

    payments = list(policy.payments.order_by(Payment.payment_date))
    assert [(p.payment_date, p.amount) for p in payments] == [
        (d2, 200),
        (d3, 300),
    ]
    # Первый платёж (d2) помечен как оплаченный
    assert payments[0].actual_payment_date == payments[0].payment_date
    # Удалённый платёж (d1)
    assert (
        Payment.select()
        .where((Payment.policy == policy) & (Payment.payment_date == d1))
        .count()
        == 0
    )
