import pytest
from datetime import date

from database.models import (
    Client,
    Policy,
    Executor,
    Deal,
    Payment,
    Income,
    DealExecutor,
)
from services.income_service import get_incomes_page, get_income_highlight_color


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
