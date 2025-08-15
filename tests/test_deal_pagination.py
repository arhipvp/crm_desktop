import datetime
import pytest
from peewee import SqliteDatabase

from database.db import db
from database.models import Client, Deal, Executor, DealExecutor
from services.deal_service import get_deals_page


@pytest.fixture()
def setup_db():
    test_db = SqliteDatabase(':memory:')
    db.initialize(test_db)
    test_db.create_tables([Client, Deal, Executor, DealExecutor])
    yield
    test_db.drop_tables([Client, Deal, Executor, DealExecutor])
    test_db.close()


def test_no_duplicate_deals_between_pages(setup_db):
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
