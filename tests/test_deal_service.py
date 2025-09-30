from datetime import date

from dateutil.relativedelta import relativedelta

from database.models import Client, Deal, Policy
from services.deal_service import add_deal_from_policy, get_open_deals, update_deal


def test_add_deal_from_policy_sets_reminder_date(
    in_memory_db, stub_drive_gateway
):
    client = Client.create(name="Клиент")
    start_date = date(2024, 1, 15)
    policy = Policy.create(
        client=client,
        policy_number="P-123",
        start_date=start_date,
    )

    deal = add_deal_from_policy(policy, gateway=stub_drive_gateway)

    assert deal.reminder_date == start_date + relativedelta(months=9)


def test_update_deal_reopen_clears_closed_reason(in_memory_db):
    client = Client.create(name="Клиент")
    deal = Deal.create(
        client=client,
        description="Закрытая сделка",
        start_date=date(2024, 5, 1),
        is_closed=True,
        closed_reason="Нет интереса",
    )

    update_deal(deal, is_closed=False, closed_reason=None)

    reopened = Deal.get_by_id(deal.id)
    assert reopened.is_closed is False
    assert reopened.closed_reason is None

    open_ids = {d.id for d in get_open_deals()}
    assert deal.id in open_ids
