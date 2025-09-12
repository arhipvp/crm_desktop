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
    DealExecutor,
)
from services.clients.client_service import build_client_query
from services.query_utils import apply_search_and_filters
from services.executor_service import get_executors_page
from services.deal_service import build_deal_query, get_deals_page
from services.income_service import get_incomes_page, get_income_highlight_color
from services.expense_service import build_expense_query
from services.task_crud import build_task_query


def _create_income_for_executor(name: str, tg_id: int) -> Income:
    client = Client.create(name=f"Client {name}")
    deal = Deal.create(
        client=client,
        description=f"Deal {name}",
        start_date=date.today(),
    )
    policy = Policy.create(
        client=client,
        deal=deal,
        policy_number=f"P{name}",
        start_date=date.today(),
    )
    payment = Payment.create(
        policy=policy,
        amount=100,
        payment_date=date.today(),
    )
    income = Income.create(payment=payment, amount=100)
    executor = Executor.create(full_name=name, tg_id=tg_id)
    DealExecutor.create(
        deal=deal,
        executor=executor,
        assigned_date=date.today(),
    )
    return income


def _make_income(contractor: str | None) -> Income:
    """Create an ``Income`` instance with an optional contractor."""

    policy = Policy(
        policy_number="123",
        contractor=contractor,
        start_date=date.today(),
    )
    payment = Payment(
        policy=policy,
        amount=100,
        payment_date=date.today(),
    )
    return Income(
        payment=payment,
        amount=10,
        received_date=date.today(),
    )


@pytest.mark.parametrize(
    "contractor, expected_color",
    [
        ("Some Corp", "#ffcccc"),
        (None, None),
    ],
)
def test_income_highlight(contractor, expected_color):
    income = _make_income(contractor)
    assert get_income_highlight_color(income) == expected_color


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


def test_filter_by_executor_full_name(in_memory_db):
    inc1 = _create_income_for_executor("Alice", 1)
    _create_income_for_executor("Bob", 2)
    result = list(
        get_incomes_page(
            page=1,
            per_page=10,
            column_filters={Executor.full_name: "Alice"},
        )
    )
    assert len(result) == 1
    assert result[0].id == inc1.id


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


def test_apply_expense_filters_field_keys(in_memory_db):
    client = Client.create(name="C1")
    deal1 = Deal.create(client=client, description="D1", start_date=date.today())
    deal2 = Deal.create(client=client, description="D2", start_date=date.today())
    policy1 = Policy.create(
        client=client, deal=deal1, policy_number="P1", start_date=date.today()
    )
    policy2 = Policy.create(
        client=client, deal=deal2, policy_number="P2", start_date=date.today()
    )
    payment1 = Payment.create(policy=policy1, amount=100, payment_date=date.today())
    payment2 = Payment.create(policy=policy2, amount=200, payment_date=date.today())
    Expense.create(payment=payment1, amount=10, expense_type="t1", policy=policy1)
    Expense.create(payment=payment2, amount=20, expense_type="t1", policy=policy2)

    query = build_expense_query(column_filters={Deal.description: "D1"})
    results = list(query)
    assert len(results) == 1
    assert results[0].policy.policy_number == "P1"


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


class TestDeals:
    @staticmethod
    def _create_deal(client: Client, description: str) -> Deal:
        return Deal.create(
            client=client,
            description=description,
            reminder_date=date.today(),
            start_date=date.today(),
        )

    def test_no_duplicate_deals_between_pages(self, in_memory_db):
        client = Client.create(name="Client")
        for i in range(5):
            self._create_deal(client, f"Deal {i}")
        page1 = get_deals_page(page=1, per_page=2, order_by="reminder_date")
        page2 = get_deals_page(page=2, per_page=2, order_by="reminder_date")
        ids1 = {d.id for d in page1}
        ids2 = {d.id for d in page2}
        assert ids1.isdisjoint(ids2)

    def test_search_deals_by_phone(self, in_memory_db):
        c1 = Client.create(name="Alice", phone="1234567890")
        c2 = Client.create(name="Bob", phone="0987654321")
        self._create_deal(c1, "Deal1")
        d2 = self._create_deal(c2, "Deal2")
        query = build_deal_query(search_text="8765")
        results = list(query)
        assert len(results) == 1
        assert results[0].id == d2.id
