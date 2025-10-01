"""Tests for functions in :mod:`services.income_service`."""

from datetime import date, timedelta

import pytest

from database.models import (
    Client,
    Policy,
    Payment,
    Income,
    Deal,
    Executor,
    DealExecutor,
)
from services.income_service import (
    mark_incomes_deleted,
    get_incomes_page,
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
            order_dir="DeSc",
        )
    )
    assert [i.id for i in page1] == [inc4.id, inc3.id]

    page2 = list(
        get_incomes_page(
            page=2,
            per_page=2,
            order_by="received_date",
            order_dir=" desc ",
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


def test_get_incomes_page_sort_by_executor_includes_income_id(in_memory_db):
    """Ordering by executor should prepend Income.id to ORDER BY for DISTINCT."""

    today = date.today()
    client = Client.create(name="C")
    deal1 = Deal.create(client=client, description="D1", start_date=today)
    deal2 = Deal.create(client=client, description="D2", start_date=today)
    ex1 = Executor.create(full_name="B", tg_id=1)
    ex2 = Executor.create(full_name="A", tg_id=2)
    DealExecutor.create(deal=deal1, executor=ex1, assigned_date=today)
    DealExecutor.create(deal=deal2, executor=ex2, assigned_date=today)
    policy1 = Policy.create(client=client, deal=deal1, policy_number="P1", start_date=today)
    policy2 = Policy.create(client=client, deal=deal2, policy_number="P2", start_date=today)
    pay1 = Payment.create(policy=policy1, amount=10, payment_date=today)
    pay2 = Payment.create(policy=policy2, amount=10, payment_date=today)
    Income.create(payment=pay1, amount=1, received_date=today)
    Income.create(payment=pay2, amount=1, received_date=today)

    query = get_incomes_page(
        page=1,
        per_page=10,
        order_by=Executor.full_name,
        order_dir="asc",
    )

    incomes = list(query)
    names = [
        i.payment.policy.deal.executors[0].executor.full_name for i in incomes
    ]
    assert names == ["A", "B"]


@pytest.mark.parametrize(
    "received_date_range",
    [
        (None, None),
        (date.today() - timedelta(days=1), date.today() + timedelta(days=1)),
    ],
)
def test_get_incomes_page_ignores_date_range_when_excluding_received(
    in_memory_db, make_policy_with_payment, received_date_range
):
    """Проверяет игнорирование диапазона дат при ``include_received``=False."""

    today = date.today()
    _, _, _policy, payment = make_policy_with_payment()
    pending_income = Income.create(payment=payment, amount=50)
    Income.create(payment=payment, amount=75, received_date=today)

    page = list(
        get_incomes_page(
            page=1,
            per_page=10,
            include_received=False,
            received_date_range=received_date_range,
            order_by="id",
            order_dir="asc",
        )
    )

    assert [income.id for income in page] == [pending_income.id]


