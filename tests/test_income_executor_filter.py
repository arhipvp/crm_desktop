import datetime

from database.models import (
    Client,
    Policy,
    Payment,
    Income,
    Deal,
    Executor,
    DealExecutor,
)
from services.income_service import get_incomes_page


def _create_income_for_executor(name: str, tg_id: int) -> Income:
    client = Client.create(name=f"Client {name}")
    deal = Deal.create(
        client=client,
        description=f"Deal {name}",
        start_date=datetime.date.today(),
    )
    policy = Policy.create(
        client=client,
        deal=deal,
        policy_number=f"P{name}",
        start_date=datetime.date.today(),
    )
    payment = Payment.create(
        policy=policy,
        amount=100,
        payment_date=datetime.date.today(),
    )
    income = Income.create(payment=payment, amount=100)
    executor = Executor.create(full_name=name, tg_id=tg_id)
    DealExecutor.create(
        deal=deal,
        executor=executor,
        assigned_date=datetime.date.today(),
    )
    return income


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
