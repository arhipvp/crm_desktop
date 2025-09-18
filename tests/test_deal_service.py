from datetime import date

from dateutil.relativedelta import relativedelta

from database.models import Client, Policy
from services.deal_service import add_deal_from_policy


def test_add_deal_from_policy_sets_reminder_date(monkeypatch, in_memory_db):
    monkeypatch.setattr(
        "services.deal_service.create_deal_folder", lambda *a, **k: (None, None)
    )
    monkeypatch.setattr(
        "services.folder_utils.move_policy_folder_to_deal", lambda *a, **k: None
    )

    client = Client.create(name="Клиент")
    start_date = date(2024, 1, 15)
    policy = Policy.create(
        client=client,
        policy_number="P-123",
        start_date=start_date,
    )

    deal = add_deal_from_policy(policy)

    assert deal.reminder_date == start_date + relativedelta(months=9)
