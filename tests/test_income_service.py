"""Tests for functions in :mod:`services.income_service`."""

from datetime import date, timedelta

import pytest

from database.models import Client, Policy, Payment, Income
from services.income_service import (
    mark_incomes_deleted,
    get_incomes_page,
    get_income_highlight_color,
)


def _create_income(*, received_date: date, amount: int, suffix: str) -> Income:
    """Create and return an ``Income`` with related records."""

    client = Client.create(name=f"Client {suffix}")
    policy = Policy.create(
        client=client,
        policy_number=f"P{suffix}",
        start_date=date.today(),
    )
    payment = Payment.create(
        policy=policy,
        amount=amount * 10,
        payment_date=date.today(),
    )
    return Income.create(
        payment=payment,
        amount=amount,
        received_date=received_date,
    )


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


def test_mark_incomes_deleted(in_memory_db):
    """Marked incomes should be excluded from ``Income.active``."""

    inc1 = _create_income(received_date=date.today(), amount=10, suffix="1")
    inc2 = _create_income(received_date=date.today(), amount=20, suffix="2")
    inc3 = _create_income(received_date=date.today(), amount=30, suffix="3")

    deleted = mark_incomes_deleted([inc1.id, inc2.id])

    assert deleted == 2
    active_ids = [i.id for i in Income.active()]
    assert active_ids == [inc3.id]


def test_get_incomes_page_pagination_and_deleted(in_memory_db):
    """``get_incomes_page`` paginates and hides deleted incomes by default."""

    today = date.today()
    inc1 = _create_income(received_date=today - timedelta(days=3), amount=10, suffix="1")
    inc2 = _create_income(received_date=today - timedelta(days=2), amount=20, suffix="2")
    inc3 = _create_income(received_date=today - timedelta(days=1), amount=30, suffix="3")
    inc4 = _create_income(received_date=today, amount=40, suffix="4")

    # delete the oldest income
    mark_incomes_deleted([inc1.id])

    page1 = list(
        get_incomes_page(
            page=1,
            per_page=2,
            order_by="received_date",
            order_dir="desc",
        )
    )
    assert [i.id for i in page1] == [inc4.id, inc3.id]

    page2 = list(
        get_incomes_page(
            page=2,
            per_page=2,
            order_by="received_date",
            order_dir="desc",
        )
    )
    assert [i.id for i in page2] == [inc2.id]

    all_incomes = list(
        get_incomes_page(
            page=1,
            per_page=10,
            order_by="received_date",
            order_dir="desc",
            show_deleted=True,
        )
    )
    assert [i.id for i in all_incomes] == [inc4.id, inc3.id, inc2.id, inc1.id]


@pytest.mark.parametrize(
    "contractor, expected_color",
    [
        ("Some Corp", "#ffcccc"),
        (None, None),
        ("—", None),
    ],
)
def test_income_highlight(contractor, expected_color):
    income = _make_income(contractor)
    assert get_income_highlight_color(income) == expected_color

