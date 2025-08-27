from datetime import date

from database.models import Client, Policy
from services.query_utils import apply_search_and_filters


def test_apply_search_and_filters_clients(in_memory_db):
    c1 = Client.create(name="Alice", phone="123", email="a@a", note="x")
    Client.create(name="Bob", phone="456", email="b@b", note="y")
    query = Client.select()
    query = apply_search_and_filters(query, Client, "Alice", {Client.phone: "123"})
    results = list(query)
    assert len(results) == 1
    assert results[0].id == c1.id


def test_apply_search_and_filters_policies(in_memory_db):
    c1 = Client.create(name="Alice")
    c2 = Client.create(name="Bob")
    p1 = Policy.create(
        client=c1,
        deal=None,
        policy_number="P1",
        start_date=date.today(),
        insurance_company="IC1",
    )
    Policy.create(
        client=c2,
        deal=None,
        policy_number="P2",
        start_date=date.today(),
        insurance_company="IC2",
    )
    query = Policy.select()
    query = apply_search_and_filters(
        query, Policy, "P1", {Policy.insurance_company: "IC1"}
    )
    results = list(query)
    assert len(results) == 1
    assert results[0].id == p1.id
