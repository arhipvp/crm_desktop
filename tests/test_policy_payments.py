import datetime
import pytest

from database.models import Client, Policy, Payment
from services import payment_service as pay_svc
from services.policies import policy_service as policy_svc


def test_sync_policy_payments_adds_and_removes(in_memory_db, mock_payments):
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


def test_update_policy_syncs_payments_and_marks_first_paid(
    in_memory_db, mock_payments, policy_folder_patches
):
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


def test_sync_policy_payments_removes_zero_when_real_exists(in_memory_db, mock_payments):
    client = Client.create(name="C")
    d0 = datetime.date(2024, 1, 1)
    d1 = datetime.date(2024, 2, 1)
    policy = Policy.create(client=client, policy_number="P", start_date=d0, end_date=d1)
    zero_payment = Payment.create(policy=policy, amount=0, payment_date=d0)

    pay_svc.sync_policy_payments(
        policy,
        [
            {"amount": 0, "payment_date": d0},
            {"amount": 100, "payment_date": d1},
        ],
    )

    payments = list(policy.payments.where(pay_svc.ACTIVE))
    assert {(p.payment_date, p.amount) for p in payments} == {(d1, 100)}
    assert (
        Payment.select()
        .where((Payment.id == zero_payment.id) & (Payment.is_deleted == True))
        .count()
        == 1
    )


def test_add_policy_rolls_back_on_payment_error(
    in_memory_db, monkeypatch, policy_folder_patches, mock_payments
):
    client = Client.create(name="C")
    d1 = datetime.date(2024, 1, 1)
    d2 = datetime.date(2024, 2, 1)

    def fail(**kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(policy_svc, "add_payment", fail)

    with pytest.raises(RuntimeError):
        policy_svc.add_policy(
            client=client,
            policy_number="P",
            start_date=d1,
            end_date=d2,
            payments=[{"amount": 100, "payment_date": d1}],
        )

    assert Policy.select().count() == 0
    assert Payment.select().count() == 0


def test_sync_policy_payments_removes_extra_duplicates(in_memory_db, mock_payments):
    client = Client.create(name="C")
    d1 = datetime.date(2024, 1, 1)
    policy = Policy.create(client=client, policy_number="P", start_date=d1, end_date=d1)
    p1 = Payment.create(policy=policy, amount=100, payment_date=d1)
    p2 = Payment.create(policy=policy, amount=100, payment_date=d1)

    pay_svc.sync_policy_payments(
        policy,
        [
            {"amount": 100, "payment_date": d1},
        ],
    )

    payments = list(policy.payments)
    assert [(p.payment_date, p.amount) for p in payments] == [(d1, 100)]
    assert Payment.select().count() == 1
    remaining_id = payments[0].id
    assert remaining_id in {p1.id, p2.id}


def test_sync_policy_payments_adds_missing_duplicates(in_memory_db, mock_payments):
    client = Client.create(name="C")
    d1 = datetime.date(2024, 1, 1)
    policy = Policy.create(client=client, policy_number="P", start_date=d1, end_date=d1)
    p1 = Payment.create(policy=policy, amount=100, payment_date=d1)

    pay_svc.sync_policy_payments(
        policy,
        [
            {"amount": 100, "payment_date": d1},
            {"amount": 100, "payment_date": d1},
        ],
    )

    payments = list(policy.payments.order_by(Payment.id))
    assert len(payments) == 2
    assert all((p.payment_date, p.amount) == (d1, 100) for p in payments)
    ids = {p.id for p in payments}
    assert p1.id in ids
    assert len(ids) == 2
