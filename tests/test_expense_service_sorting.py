import datetime

import pytest

from database.models import Client, Expense, Payment, Policy
from services import expense_service


@pytest.mark.parametrize(
    "order_by, order_dir, expected_order",
    [
        (Payment.amount, "asc", ("second", "first")),
        (Payment.amount, "desc", ("first", "second")),
        (Payment.payment_date, "asc", ("second", "first")),
        (Payment.payment_date, "desc", ("first", "second")),
    ],
)
def test_build_expense_query_orders_by_payment_fields(
    order_by, order_dir, expected_order, in_memory_db
):
    client = Client.create(name="Test client")
    policy = Policy.create(
        client=client,
        deal=None,
        policy_number="P-001",
        start_date=datetime.date(2023, 1, 1),
    )

    payment_first = Payment.create(
        policy=policy,
        amount=100,
        payment_date=datetime.date(2024, 1, 10),
    )
    payment_second = Payment.create(
        policy=policy,
        amount=50,
        payment_date=datetime.date(2023, 12, 31),
    )

    expense_first = Expense.create(
        payment=payment_first,
        policy=policy,
        amount=10,
        expense_type="fee",
        expense_date=datetime.date(2024, 1, 11),
    )
    expense_second = Expense.create(
        payment=payment_second,
        policy=policy,
        amount=5,
        expense_type="fee",
        expense_date=datetime.date(2023, 12, 31),
    )

    expected_map = {
        "first": expense_first.id,
        "second": expense_second.id,
    }

    result = list(
        expense_service.build_expense_query(
            order_by=order_by,
            order_dir=order_dir,
        )
    )

    assert [item.id for item in result] == [expected_map[key] for key in expected_order]
