import pytest
import datetime

from database.models import Client, Policy, Executor, Deal
from services.clients.client_service import build_client_query
from services.query_utils import apply_search_and_filters
from services.executor_service import get_executors_page
from services.deal_service import build_deal_query, get_deals_page


TODAY = datetime.date(2024, 1, 1)


def _create_deal(client: Client, description: str) -> Deal:
    return Deal.create(
        client=client,
        description=description,
        reminder_date=TODAY,
        start_date=TODAY,
    )


def test_client_search_with_filters(in_memory_db):
    Client.create(name="Bob", phone="456", email="b@b", note="y")
    Client.create(name="Alice", phone="123", email="a@a", note="x")
    query = apply_search_and_filters(
        Client.select(), Client, "Alice", {Client.phone: "123"}
    )
    assert [c.name for c in query] == ["Alice"]


@pytest.mark.parametrize("order_by", ["name", "phone", "email"])
def test_client_sorting(in_memory_db, order_by):
    Client.create(name="Bob", phone="456", email="b@b", note="y")
    Client.create(name="Alice", phone="123", email="a@a", note="x")
    query = build_client_query(order_by=order_by, order_dir="asc")
    assert [c.name for c in query] == ["Alice", "Bob"]


def test_apply_search_and_filters_policies(in_memory_db):
    c1 = Client.create(name="Alice")
    c2 = Client.create(name="Bob")
    p1 = Policy.create(
        client=c1,
        deal=None,
        policy_number="P1",
        start_date=TODAY,
        insurance_company="IC1",
    )
    Policy.create(
        client=c2,
        deal=None,
        policy_number="P2",
        start_date=TODAY,
        insurance_company="IC2",
    )
    query = Policy.select()
    query = apply_search_and_filters(
        query, Policy, "P1", {Policy.insurance_company: "IC1"}
    )
    results = list(query)
    assert len(results) == 1
    assert results[0].id == p1.id


def test_get_executors_page_filters(in_memory_db):
    e1 = Executor.create(full_name="Alice", tg_id=1, is_active=True)
    Executor.create(full_name="Bob", tg_id=2, is_active=True)

    results = list(
        get_executors_page(page=1, per_page=10, search_text="Alice")
    )
    assert len(results) == 1
    assert results[0].id == e1.id

    results = list(
        get_executors_page(
            page=1,
            per_page=10,
            column_filters={"full_name": "Bob"},
        )
    )
    assert len(results) == 1
    assert results[0].full_name == "Bob"


def test_no_duplicate_deals_between_pages(in_memory_db):
    client = Client.create(name="Client")
    for i in range(5):
        _create_deal(client, f"Deal {i}")
    page1 = get_deals_page(page=1, per_page=2, order_by="reminder_date")
    page2 = get_deals_page(page=2, per_page=2, order_by="reminder_date")
    ids1 = {d.id for d in page1}
    ids2 = {d.id for d in page2}
    assert ids1.isdisjoint(ids2)


def test_search_deals_by_phone(in_memory_db):
    c1 = Client.create(name="Alice", phone="1234567890")
    c2 = Client.create(name="Bob", phone="0987654321")
    _create_deal(c1, "Deal1")
    d2 = _create_deal(c2, "Deal2")
    query = build_deal_query(search_text="8765")
    results = list(query)
    assert len(results) == 1
    assert results[0].id == d2.id
