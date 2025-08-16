import datetime
import pytest
from peewee import SqliteDatabase

from database.db import db
from database.models import Client, Policy, Payment, Income, Expense
from services import policy_service as ps


@pytest.fixture()
def setup_db(monkeypatch):
    test_db = SqliteDatabase(':memory:')
    db.initialize(test_db)
    test_db.create_tables([Client, Policy, Payment, Income, Expense])
    test_db.execute_sql('DROP INDEX IF EXISTS "policy_policy_number"')
    monkeypatch.setattr(ps, 'create_policy_folder', lambda *a, **k: None)
    monkeypatch.setattr(ps, 'open_folder', lambda *a, **k: None)
    monkeypatch.setattr('services.folder_utils.rename_policy_folder', lambda *a, **k: (None, None))
    yield
    test_db.drop_tables([Client, Policy, Payment, Income, Expense])
    test_db.close()


def test_create_policy_ignores_deleted_duplicates(setup_db):
    client = Client.create(name='C')
    start = datetime.date(2024, 1, 1)
    end = datetime.date(2025, 1, 1)
    Policy.create(
        client=client,
        policy_number='P',
        start_date=start,
        end_date=end,
        is_deleted=True,
    )
    policy = ps.add_policy(
        client=client,
        policy_number='P',
        start_date=start,
        end_date=end,
    )
    assert policy.policy_number == 'P'
    assert policy.is_deleted is False
    assert Policy.select().count() == 2
