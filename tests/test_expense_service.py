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


def test_income_and_expense_sums(in_memory_db, make_policy_with_payment):
    """Суммы доходов и расходов агрегируются корректно."""

    _, _, policy, payment = make_policy_with_payment()
    inc1 = Income.create(payment=payment, amount=100)
    inc2 = Income.create(payment=payment, amount=50)
    exp1 = Expense.create(
        payment=payment, amount=30, expense_type="e1", policy=policy
    )
    exp2 = Expense.create(
        payment=payment, amount=20, expense_type="e2", policy=policy
    )

    total_income = inc1.amount + inc2.amount
    total_expense = exp1.amount + exp2.amount

    rows = list(build_expense_query())
    row1 = next(r for r in rows if r.id == exp1.id)
    row2 = next(r for r in rows if r.id == exp2.id)

    assert row1.income_total == total_income
    assert row2.income_total == total_income
    assert row1.other_expense_total == exp2.amount
    assert row2.other_expense_total == exp1.amount
    expected_net = total_income - total_expense
    assert row1.net_income == expected_net
    assert row2.net_income == expected_net

