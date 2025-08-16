import datetime
import pytest
from peewee import SqliteDatabase

from database.db import db
from database.models import Client, Policy, Payment, Income, Expense
from services import policy_service as ps
from services.payment_service import add_payment

@pytest.fixture()
def setup_db(monkeypatch):
    test_db = SqliteDatabase(':memory:')
    db.initialize(test_db)
    test_db.create_tables([Client, Policy, Payment, Income, Expense])
    monkeypatch.setattr(ps, 'create_policy_folder', lambda *a, **k: None)
    monkeypatch.setattr(ps, 'open_folder', lambda *a, **k: None)
    monkeypatch.setattr('services.folder_utils.rename_policy_folder', lambda *a, **k: (None, None))
    yield
    test_db.drop_tables([Client, Policy, Payment, Income, Expense])
    test_db.close()


def test_policy_merge_additional_payments(setup_db):
    client = Client.create(name='C')
    start = datetime.date(2024, 1, 1)
    end = datetime.date(2025, 1, 1)
    initial_payments = [
        {'amount': 100, 'payment_date': start},
        {'amount': 150, 'payment_date': start + datetime.timedelta(days=30)},
    ]
    policy = ps.add_policy(
        client=client,
        policy_number='P',
        start_date=start,
        end_date=end,
        payments=initial_payments,
    )
    assert policy.payments.count() == 2

    extra_payments = [
        {'amount': 200, 'payment_date': start + datetime.timedelta(days=60)},
    ]
    with pytest.raises(ps.DuplicatePolicyError) as exc:
        ps.add_policy(
            client=client,
            policy_number='P',
            start_date=start,
            end_date=end,
            insurance_company='NewCo',
            payments=extra_payments,
        )
    existing = exc.value.existing_policy
    ps.update_policy(existing, insurance_company='NewCo')
    for p in extra_payments:
        add_payment(policy=existing, amount=p['amount'], payment_date=p['payment_date'])
    amounts = sorted(pay.amount for pay in existing.payments)
    assert amounts == [100, 150, 200]
    assert existing.insurance_company == 'NewCo'


def test_recreate_after_delete(setup_db):
    client = Client.create(name='C')
    start = datetime.date(2024, 1, 1)
    end = datetime.date(2025, 1, 1)
    policy = ps.add_policy(
        client=client,
        policy_number='P',
        start_date=start,
        end_date=end,
        payments=[{'amount': 50, 'payment_date': start}],
    )
    pid = policy.id
    ps.mark_policy_deleted(pid)
    new_policy = ps.add_policy(
        client=client,
        policy_number='P',
        start_date=start,
        end_date=end,
        payments=[{'amount': 60, 'payment_date': start + datetime.timedelta(days=10)}],
    )
    assert new_policy.policy_number == 'P'
    assert new_policy.id != pid
