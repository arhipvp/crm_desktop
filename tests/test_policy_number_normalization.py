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
    monkeypatch.setattr(ps, 'create_policy_folder', lambda *a, **k: None)
    monkeypatch.setattr(ps, 'open_folder', lambda *a, **k: None)
    monkeypatch.setattr('services.folder_utils.rename_policy_folder', lambda *a, **k: (None, None))
    yield
    test_db.drop_tables([Client, Policy, Payment, Income, Expense])
    test_db.close()


def test_duplicate_detected_with_normalized_policy_number(setup_db):
    client = Client.create(name='C')
    start = datetime.date(2024, 1, 1)
    end = datetime.date(2025, 1, 1)
    ps.add_policy(
        client=client,
        policy_number='ab123',
        start_date=start,
        end_date=end,
    )
    with pytest.raises(ps.DuplicatePolicyError) as exc:
        ps.add_policy(
            client=client,
            policy_number='AB 123',
            start_date=start,
            end_date=end,
        )
    assert exc.value.existing_policy.policy_number == 'AB123'
