from datetime import date

from database.models import Client, Deal
from services.deal_service import build_deal_query


def test_search_deals_by_phone(in_memory_db):
    c1 = Client.create(name="Alice", phone="1234567890")
    c2 = Client.create(name="Bob", phone="0987654321")
    d1 = Deal.create(
        client=c1,
        description="Deal1",
        reminder_date=date.today(),
        start_date=date.today(),
    )
    d2 = Deal.create(
        client=c2,
        description="Deal2",
        reminder_date=date.today(),
        start_date=date.today(),
    )
    query = build_deal_query(search_text="8765")
    results = list(query)
    assert len(results) == 1
    assert results[0].id == d2.id
