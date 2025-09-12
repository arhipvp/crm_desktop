import datetime
from datetime import date

from database.models import Client, Deal
from services.deal_service import build_deal_query, get_deals_page


def test_no_duplicate_deals_between_pages(in_memory_db):
    client = Client.create(name='Client')
    for i in range(5):
        Deal.create(
            client=client,
            description=f'Deal {i}',
            reminder_date=datetime.date(2024, 1, 1),
            start_date=datetime.date(2024, 1, 1),
        )
    page1 = get_deals_page(page=1, per_page=2, order_by='reminder_date')
    page2 = get_deals_page(page=2, per_page=2, order_by='reminder_date')
    ids1 = {d.id for d in page1}
    ids2 = {d.id for d in page2}
    assert ids1.isdisjoint(ids2)


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
