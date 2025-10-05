"""Tests for :mod:`services.expense_service`."""

from datetime import date, timedelta
import logging

import pytest

from database.models import Expense, Income
from services.expense_service import INCOME_TOTAL, build_expense_query, update_expense


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


@pytest.mark.parametrize(
    "expense_date_range",
    [
        (None, None),
        (date.today() - timedelta(days=1), date.today() + timedelta(days=1)),
    ],
)
def test_build_expense_query_ignores_date_range_when_excluding_paid(
    in_memory_db, make_policy_with_payment, expense_date_range
):
    """Проверяет, что фильтр по дате не применяется, если ``include_paid``=False."""

    _, _, policy, payment = make_policy_with_payment()
    pending = Expense.create(
        payment=payment,
        amount=50,
        expense_type="отложен",
        policy=policy,
    )
    Expense.create(
        payment=payment,
        amount=75,
        expense_type="оплачен",
        policy=policy,
        expense_date=date.today(),
    )

    results = list(
        build_expense_query(
            include_paid=False,
            expense_date_range=expense_date_range,
            order_by="id",
            order_dir="asc",
        )
    )

    assert [expense.id for expense in results] == [pending.id]


def test_update_expense_allows_clearing_nullable_fields(
    in_memory_db, make_policy_with_payment, caplog
):
    caplog.set_level(logging.INFO, logger="services.expense_service")
    _, _, policy, payment = make_policy_with_payment()
    expense = Expense.create(
        payment=payment,
        policy=policy,
        amount=50,
        expense_type="тест",
        expense_date=date.today(),
        note="Комментарий",
    )

    update_expense(expense, expense_date=None, note=None)

    updated = Expense.get_by_id(expense.id)

    assert updated.expense_date is None
    assert updated.note is None

    log_messages = [record.getMessage() for record in caplog.records]
    assert any("'expense_date': None" in message for message in log_messages)
    assert any("'note': None" in message for message in log_messages)


def test_income_total_filter_accepts_multiple_values(
    in_memory_db, make_policy_with_payment
):
    """Фильтр по ``income_total`` строит OR-условие для нескольких значений."""

    _, _, policy1, payment1 = make_policy_with_payment()
    Income.create(payment=payment1, amount=123)
    expense1 = Expense.create(
        payment=payment1, policy=policy1, amount=10, expense_type="первый"
    )

    _, _, policy2, payment2 = make_policy_with_payment(
        client_kwargs={"name": "C2"},
        deal_kwargs={"description": "D2"},
        policy_kwargs={"policy_number": "P2"},
    )
    Income.create(payment=payment2, amount=456)
    expense2 = Expense.create(
        payment=payment2, policy=policy2, amount=15, expense_type="второй"
    )

    query = build_expense_query(
        column_filters={INCOME_TOTAL: ["123", "456"]},
        order_by="id",
        order_dir="asc",
    )

    sql, params = query.sql()
    upper_sql = sql.upper()
    assert "HAVING" in upper_sql
    having_part = upper_sql.split("HAVING", 1)[1]
    assert having_part.count("LIKE ?") == 2
    assert " OR " in having_part
    assert params.count("%123%") == 1
    assert params.count("%456%") == 1

    results = list(query)
    assert {row.id for row in results} == {expense1.id, expense2.id}

