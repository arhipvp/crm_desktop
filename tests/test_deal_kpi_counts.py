from datetime import date, timedelta
from decimal import Decimal

from database.models import (
    Client,
    Deal,
    DealExecutor,
    Expense,
    Executor,
    Income,
    Payment,
    Policy,
    Task,
)
from services.deal_metrics import get_deal_kpi_metrics


def _track_query_count(monkeypatch, database):
    counter = {"count": 0}
    original_execute_sql = database.__class__.execute_sql

    def counting_execute_sql(self, sql, params=None, commit=True):
        counter["count"] += 1
        return original_execute_sql(self, sql, params, commit)

    monkeypatch.setattr(database.__class__, "execute_sql", counting_execute_sql)
    return counter


def test_get_deal_kpi_metrics_aggregates_all_entities(in_memory_db, monkeypatch):
    today = date.today()
    client = Client.create(name="KPI Client")
    deal = Deal.create(client=client, description="Main Deal", start_date=today)
    other_deal = Deal.create(client=client, description="Other Deal", start_date=today)

    # Policies
    policy_active = Policy.create(
        client=client,
        deal=deal,
        policy_number="POL-ACT",
        start_date=today,
    )
    Policy.create(
        client=client,
        deal=deal,
        policy_number="POL-FUT",
        start_date=today,
        end_date=today + timedelta(days=10),
    )
    Policy.create(
        client=client,
        deal=deal,
        policy_number="POL-END",
        start_date=today,
        end_date=today - timedelta(days=1),
    )
    other_policy = Policy.create(
        client=client,
        deal=other_deal,
        policy_number="POL-OTHER",
        start_date=today,
    )

    # Payments
    payment_open = Payment.create(
        policy=policy_active,
        amount=Decimal("100"),
        payment_date=today,
    )
    payment_closed = Payment.create(
        policy=policy_active,
        amount=Decimal("50"),
        payment_date=today,
        actual_payment_date=today,
    )
    other_payment = Payment.create(
        policy=other_policy,
        amount=Decimal("25"),
        payment_date=today,
    )

    # Incomes
    Income.create(payment=payment_open, amount=Decimal("30"))
    Income.create(
        payment=payment_open,
        amount=Decimal("40"),
        received_date=today,
    )
    Income.create(payment=other_payment, amount=Decimal("5"))

    # Expenses
    Expense.create(
        payment=payment_closed,
        policy=policy_active,
        amount=Decimal("10"),
        expense_type="pending",
    )
    Expense.create(
        payment=payment_closed,
        policy=policy_active,
        amount=Decimal("5"),
        expense_type="done",
        expense_date=today,
    )
    Expense.create(
        payment=other_payment,
        policy=other_policy,
        amount=Decimal("3"),
        expense_type="other",
    )

    # Tasks
    Task.create(title="Open", due_date=today, deal=deal, is_done=False)
    Task.create(title="Closed", due_date=today, deal=deal, is_done=True)
    Task.create(title="Extra", due_date=today, deal=other_deal, is_done=False)

    # Executor
    executor = Executor.create(full_name="Иван Иванов", tg_id=123, is_active=True)
    DealExecutor.create(deal=deal, executor=executor, assigned_date=today)

    counter = _track_query_count(monkeypatch, in_memory_db)
    metrics = get_deal_kpi_metrics(deal.id)

    assert counter["count"] == 1
    assert metrics["policies_open"] == 2
    assert metrics["policies_closed"] == 1
    assert metrics["payments_open"] == 1
    assert metrics["payments_closed"] == 1
    assert metrics["payments_expected"] == Decimal("100")
    assert metrics["payments_received"] == Decimal("50")
    assert metrics["incomes_open"] == 1
    assert metrics["incomes_closed"] == 1
    assert metrics["incomes_expected"] == Decimal("30")
    assert metrics["incomes_received"] == Decimal("40")
    assert metrics["expenses_open"] == 1
    assert metrics["expenses_closed"] == 1
    assert metrics["expenses_planned"] == Decimal("10")
    assert metrics["expenses_spent"] == Decimal("5")
    assert metrics["tasks_open"] == 1
    assert metrics["tasks_closed"] == 1
    assert metrics["executor_full_name"] == "Иван Иванов"


def test_get_deal_kpi_metrics_returns_defaults_for_empty_deal(
    in_memory_db, monkeypatch
):
    today = date.today()
    client = Client.create(name="Empty Client")
    deal = Deal.create(client=client, description="Empty Deal", start_date=today)

    counter = _track_query_count(monkeypatch, in_memory_db)
    metrics = get_deal_kpi_metrics(deal.id)

    assert counter["count"] == 1
    assert metrics["policies_open"] == 0
    assert metrics["payments_expected"] == Decimal("0")
    assert metrics["incomes_received"] == Decimal("0")
    assert metrics["expenses_spent"] == Decimal("0")
    assert metrics["tasks_open"] == 0
    assert metrics["executor_full_name"] is None
