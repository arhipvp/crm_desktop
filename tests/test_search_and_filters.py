import pytest
from datetime import date

from database.models import (
    Client,
    Policy,
    Executor,
    Deal,
    Payment,
    Income,
    Expense,
    Task,
)
from services.clients.client_service import build_client_query
from services.query_utils import apply_search_and_filters
from services.executor_service import get_executors_page
from services.income_service import get_incomes_page
from services.expense_service import build_expense_query
from services.task_crud import build_task_query


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


@pytest.mark.parametrize(
    "search, expected",
    [
        ("P1", "P1"),
        ("Alice", "P1"),
        ("DealA", "P1"),
        ("NoteA", "P1"),
    ],
)
def test_income_search_related_models(in_memory_db, search, expected):
    client1 = Client.create(name="Alice")
    deal1 = Deal.create(
        client=client1, description="DealA", start_date=date.today()
    )
    policy1 = Policy.create(
        client=client1,
        deal=deal1,
        policy_number="P1",
        start_date=date.today(),
        note="NoteA",
    )
    payment1 = Payment.create(
        policy=policy1, amount=100, payment_date=date.today()
    )
    Income.create(payment=payment1, amount=10)

    client2 = Client.create(name="Bob")
    deal2 = Deal.create(
        client=client2, description="DealB", start_date=date.today()
    )
    policy2 = Policy.create(
        client=client2,
        deal=deal2,
        policy_number="P2",
        start_date=date.today(),
        note="NoteB",
    )
    payment2 = Payment.create(
        policy=policy2, amount=200, payment_date=date.today()
    )
    Income.create(payment=payment2, amount=20)

    query = get_incomes_page(page=1, per_page=10, search_text=search)
    results = list(query)
    assert [r.payment.policy.policy_number for r in results] == [expected]


@pytest.mark.parametrize(
    "search, expected",
    [
        ("P1", "P1"),
        ("Alice", "P1"),
        ("DealA", "P1"),
        ("NoteA", "P1"),
    ],
)
def test_expense_search_related_models(in_memory_db, search, expected):
    client1 = Client.create(name="Alice")
    deal1 = Deal.create(
        client=client1, description="DealA", start_date=date.today()
    )
    policy1 = Policy.create(
        client=client1,
        deal=deal1,
        policy_number="P1",
        start_date=date.today(),
        note="NoteA",
    )
    payment1 = Payment.create(
        policy=policy1, amount=100, payment_date=date.today()
    )
    Expense.create(
        payment=payment1, amount=10, expense_type="t", policy=policy1
    )

    client2 = Client.create(name="Bob")
    deal2 = Deal.create(
        client=client2, description="DealB", start_date=date.today()
    )
    policy2 = Policy.create(
        client=client2,
        deal=deal2,
        policy_number="P2",
        start_date=date.today(),
        note="NoteB",
    )
    payment2 = Payment.create(
        policy=policy2, amount=200, payment_date=date.today()
    )
    Expense.create(
        payment=payment2, amount=20, expense_type="t", policy=policy2
    )

    query = build_expense_query(search_text=search)
    results = list(query)
    assert [r.policy.policy_number for r in results] == [expected]


@pytest.mark.parametrize(
    "search, expected",
    [
        ("T1", "T1"),
        ("N1", "T1"),
        ("DealA", "T1"),
        ("P1", "T1"),
        ("Alice", "T1"),
    ],
)
def test_task_search_related_models(in_memory_db, search, expected):
    client1 = Client.create(name="Alice")
    deal1 = Deal.create(
        client=client1, description="DealA", start_date=date.today()
    )
    policy1 = Policy.create(
        client=client1, deal=deal1, policy_number="P1", start_date=date.today()
    )
    Task.create(
        title="T1",
        note="N1",
        deal=deal1,
        policy=policy1,
        due_date=date.today(),
    )

    client2 = Client.create(name="Bob")
    deal2 = Deal.create(
        client=client2, description="DealB", start_date=date.today()
    )
    policy2 = Policy.create(
        client=client2, deal=deal2, policy_number="P2", start_date=date.today()
    )
    Task.create(
        title="T2",
        note="N2",
        deal=deal2,
        policy=policy2,
        due_date=date.today(),
    )

    query = build_task_query(search_text=search)
    results = list(query)
    assert [r.title for r in results] == [expected]
