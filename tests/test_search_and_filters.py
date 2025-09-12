import pytest
from datetime import date

from database.models import Client, Policy, Executor
from services.clients.client_service import build_client_query
from services.query_utils import apply_search_and_filters
from services.executor_service import get_executors_page


@pytest.mark.parametrize(
    "query_builder, expected_names",
    [
        (
            lambda: apply_search_and_filters(
                Client.select(), Client, "Alice", {Client.phone: "123"}
            ),
            ["Alice"],
        ),
        (
            lambda: build_client_query(order_by="name", order_dir="asc"),
            ["Alice", "Bob"],
        ),
    ],
)
def test_client_search_and_sorting(in_memory_db, query_builder, expected_names):
    Client.create(name="Bob", phone="456", email="b@b", note="y")
    Client.create(name="Alice", phone="123", email="a@a", note="x")
    query = query_builder()
    assert [c.name for c in query] == expected_names


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
