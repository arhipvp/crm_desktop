"""Проверки агрегатов KPI по сделке."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from database.models import (
    Client,
    Deal,
    Policy,
    Payment,
    Task,
    Income,
    Expense,
)
from services.task_crud import get_task_counts_by_deal_id
from services.policies.policy_service import get_policy_counts_by_deal_id
from services.payment_service import get_payment_counts_by_deal_id
from services.income_service import get_income_counts_by_deal_id
from services.expense_service import get_expense_counts_by_deal_id


def _track_query_count(monkeypatch, database):
    counter = {"count": 0}
    original_execute_sql = database.__class__.execute_sql

    def counting_execute_sql(self, sql, params=None, commit=True):
        counter["count"] += 1
        return original_execute_sql(self, sql, params, commit)

    monkeypatch.setattr(database.__class__, "execute_sql", counting_execute_sql)
    return counter


def test_get_task_counts_uses_single_query(in_memory_db, monkeypatch):
    client = Client.create(name="Task Client")
    deal = Deal.create(
        client=client,
        description="Task Deal",
        start_date=date.today(),
    )
    other_deal = Deal.create(
        client=client,
        description="Other Deal",
        start_date=date.today(),
    )

    Task.create(title="Open", due_date=date.today(), deal=deal, is_done=False)
    Task.create(title="Closed", due_date=date.today(), deal=deal, is_done=True)
    Task.create(title="Extra", due_date=date.today(), deal=other_deal, is_done=False)

    counter = _track_query_count(monkeypatch, in_memory_db)
    assert get_task_counts_by_deal_id(deal.id) == (1, 1)
    assert counter["count"] == 1


def test_get_policy_counts_uses_single_query(in_memory_db, monkeypatch):
    client = Client.create(name="Policy Client")
    deal = Deal.create(
        client=client,
        description="Policy Deal",
        start_date=date.today(),
    )
    other_deal = Deal.create(
        client=client,
        description="Policy Deal 2",
        start_date=date.today(),
    )

    Policy.create(
        client=client,
        deal=deal,
        policy_number="POL1",
        start_date=date.today(),
    )
    Policy.create(
        client=client,
        deal=deal,
        policy_number="POL2",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=10),
    )
    Policy.create(
        client=client,
        deal=deal,
        policy_number="POL3",
        start_date=date.today(),
        end_date=date.today() - timedelta(days=1),
    )
    Policy.create(
        client=client,
        deal=other_deal,
        policy_number="POL4",
        start_date=date.today(),
    )

    counter = _track_query_count(monkeypatch, in_memory_db)
    assert get_policy_counts_by_deal_id(deal.id) == (2, 1)
    assert counter["count"] == 1


def test_get_payment_counts_uses_single_query(in_memory_db, monkeypatch):
    client = Client.create(name="Payment Client")
    deal = Deal.create(
        client=client,
        description="Payment Deal",
        start_date=date.today(),
    )
    other_deal = Deal.create(
        client=client,
        description="Payment Deal 2",
        start_date=date.today(),
    )

    policy = Policy.create(
        client=client,
        deal=deal,
        policy_number="PAY1",
        start_date=date.today(),
    )
    other_policy = Policy.create(
        client=client,
        deal=other_deal,
        policy_number="PAY2",
        start_date=date.today(),
    )

    Payment.create(
        policy=policy,
        amount=Decimal("100"),
        payment_date=date.today(),
    )
    Payment.create(
        policy=policy,
        amount=Decimal("50"),
        payment_date=date.today(),
        actual_payment_date=date.today(),
    )
    Payment.create(
        policy=other_policy,
        amount=Decimal("25"),
        payment_date=date.today(),
    )

    counter = _track_query_count(monkeypatch, in_memory_db)
    assert get_payment_counts_by_deal_id(deal.id) == (1, 1)
    assert counter["count"] == 1


def test_get_income_counts_uses_single_query(in_memory_db, monkeypatch):
    client = Client.create(name="Income Client")
    deal = Deal.create(
        client=client,
        description="Income Deal",
        start_date=date.today(),
    )
    other_deal = Deal.create(
        client=client,
        description="Income Deal 2",
        start_date=date.today(),
    )

    policy = Policy.create(
        client=client,
        deal=deal,
        policy_number="INC1",
        start_date=date.today(),
    )
    other_policy = Policy.create(
        client=client,
        deal=other_deal,
        policy_number="INC2",
        start_date=date.today(),
    )

    payment = Payment.create(
        policy=policy,
        amount=Decimal("10"),
        payment_date=date.today(),
    )
    other_payment = Payment.create(
        policy=other_policy,
        amount=Decimal("20"),
        payment_date=date.today(),
    )

    Income.create(payment=payment, amount=Decimal("5"))
    Income.create(
        payment=payment,
        amount=Decimal("7"),
        received_date=date.today(),
    )
    Income.create(payment=other_payment, amount=Decimal("3"))

    counter = _track_query_count(monkeypatch, in_memory_db)
    assert get_income_counts_by_deal_id(deal.id) == (1, 1)
    assert counter["count"] == 1


def test_get_expense_counts_uses_single_query(in_memory_db, monkeypatch):
    client = Client.create(name="Expense Client")
    deal = Deal.create(
        client=client,
        description="Expense Deal",
        start_date=date.today(),
    )
    other_deal = Deal.create(
        client=client,
        description="Expense Deal 2",
        start_date=date.today(),
    )

    policy = Policy.create(
        client=client,
        deal=deal,
        policy_number="EXP1",
        start_date=date.today(),
    )
    other_policy = Policy.create(
        client=client,
        deal=other_deal,
        policy_number="EXP2",
        start_date=date.today(),
    )

    payment = Payment.create(
        policy=policy,
        amount=Decimal("15"),
        payment_date=date.today(),
    )
    other_payment = Payment.create(
        policy=other_policy,
        amount=Decimal("30"),
        payment_date=date.today(),
    )

    Expense.create(
        payment=payment,
        policy=policy,
        amount=Decimal("5"),
        expense_type="open",
    )
    Expense.create(
        payment=payment,
        policy=policy,
        amount=Decimal("8"),
        expense_type="closed",
        expense_date=date.today(),
    )
    Expense.create(
        payment=other_payment,
        policy=other_policy,
        amount=Decimal("2"),
        expense_type="extra",
    )

    counter = _track_query_count(monkeypatch, in_memory_db)
    assert get_expense_counts_by_deal_id(deal.id) == (1, 1)
    assert counter["count"] == 1

