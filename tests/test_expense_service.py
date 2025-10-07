"""Tests for :mod:`services.expense_service`."""

from datetime import date, timedelta
from decimal import Decimal
import logging

import pytest

from database.db import db
from database.models import Expense, Income
from services.expense_service import (
    INCOME_TOTAL,
    fetch_expenses_page_with_total,
    build_expense_query,
    update_expense,
    get_expense_amounts_by_deal_id,
)


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


def test_fetch_expenses_page_with_total_paginates(in_memory_db, make_policy_with_payment):
    """``fetch_expenses_page_with_total`` возвращает страницу и общее количество."""

    _, _, policy, payment = make_policy_with_payment()
    today = date.today()
    exp1 = Expense.create(
        payment=payment,
        policy=policy,
        amount=Decimal("10"),
        expense_type="e1",
        expense_date=today - timedelta(days=3),
    )
    exp2 = Expense.create(
        payment=payment,
        policy=policy,
        amount=Decimal("20"),
        expense_type="e2",
        expense_date=today - timedelta(days=2),
    )
    exp3 = Expense.create(
        payment=payment,
        policy=policy,
        amount=Decimal("30"),
        expense_type="e3",
        expense_date=today - timedelta(days=1),
    )
    exp4 = Expense.create(
        payment=payment,
        policy=policy,
        amount=Decimal("40"),
        expense_type="e4",
        expense_date=today,
    )

    Expense.update(is_deleted=True).where(Expense.id == exp1.id).execute()

    page1_query, total = fetch_expenses_page_with_total(
        page=1,
        per_page=2,
        order_by="expense_date",
        order_dir="desc",
    )
    page1 = list(page1_query)
    assert [expense.id for expense in page1] == [exp4.id, exp3.id]
    assert total == 3

    page2_query, total_page2 = fetch_expenses_page_with_total(
        page=2,
        per_page=2,
        order_by="expense_date",
        order_dir="desc",
    )
    page2 = list(page2_query)
    assert [expense.id for expense in page2] == [exp2.id]
    assert total_page2 == 3

    all_query, total_all = fetch_expenses_page_with_total(
        page=1,
        per_page=10,
        order_by="expense_date",
        order_dir="desc",
        show_deleted=True,
    )
    all_expenses = list(all_query)
    assert [expense.id for expense in all_expenses] == [
        exp4.id,
        exp3.id,
        exp2.id,
        exp1.id,
    ]
    assert total_all == 4


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


@pytest.mark.usefixtures("db_transaction")
def test_get_expense_amounts_by_deal_id_single_query(
    make_policy_with_payment, monkeypatch
):
    """Расходы по сделке суммируются одним SQL-запросом."""

    client, deal, policy1, payment1 = make_policy_with_payment(
        policy_kwargs={"policy_number": "EXP-1"},
        payment_kwargs={"amount": 100},
    )
    Expense.create(
        payment=payment1,
        policy=policy1,
        amount=40,
        expense_type="pending-1",
    )
    Expense.create(
        payment=payment1,
        policy=policy1,
        amount=60,
        expense_type="spent-1",
        expense_date=date(2024, 1, 5),
    )

    _, _, policy2, payment2 = make_policy_with_payment(
        client=client,
        deal=deal,
        policy_kwargs={"policy_number": "EXP-2"},
        payment_kwargs={"amount": 200},
    )
    Expense.create(
        payment=payment2,
        policy=policy2,
        amount=20,
        expense_type="pending-2",
    )
    Expense.create(
        payment=payment2,
        policy=policy2,
        amount=50,
        expense_type="spent-2",
        expense_date=date(2024, 2, 10),
    )

    database = db.obj
    executed: list[str] = []
    original_execute_sql = database.execute_sql

    def spy(sql, params=None, *args, **kwargs):
        executed.append(sql)
        return original_execute_sql(sql, params, *args, **kwargs)

    monkeypatch.setattr(database, "execute_sql", spy)

    planned, spent = get_expense_amounts_by_deal_id(deal.id)

    assert planned == Decimal("60")
    assert spent == Decimal("110")
    assert len(executed) == 1
    assert "CASE" in executed[0].upper()

