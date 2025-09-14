"""Tests for :mod:`services.expense_service`."""

from database.models import Expense, Income
from services.expense_service import build_expense_query


def test_other_expense_total_excludes_current(in_memory_db, make_policy_with_payment):
    """``other_expense_total`` should not include the current expense."""

    _, _, policy, payment = make_policy_with_payment()
    Income.create(payment=payment, amount=100)
    discount = Expense.create(
        payment=payment, amount=15, expense_type="скидка", policy=policy
    )
    payout = Expense.create(
        payment=payment, amount=20, expense_type="выплата", policy=policy
    )

    rows = list(build_expense_query())
    discount_row = next(r for r in rows if r.id == discount.id)
    payout_row = next(r for r in rows if r.id == payout.id)

    assert discount_row.other_expense_total == payout.amount
    assert payout_row.other_expense_total == discount.amount

