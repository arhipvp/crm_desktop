"""Aggregated KPI metrics for deal-related entities."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from peewee import Case, JOIN, fn

from database.models import (
    Deal,
    DealExecutor,
    Executor,
    Expense,
    Income,
    Payment,
    Policy,
    Task,
)


DecimalLike = Any


DEFAULT_METRICS: dict[str, Any] = {
    "policies_open": 0,
    "policies_closed": 0,
    "payments_open": 0,
    "payments_closed": 0,
    "payments_expected": Decimal("0"),
    "payments_received": Decimal("0"),
    "incomes_open": 0,
    "incomes_closed": 0,
    "incomes_expected": Decimal("0"),
    "incomes_received": Decimal("0"),
    "expenses_open": 0,
    "expenses_closed": 0,
    "expenses_planned": Decimal("0"),
    "expenses_spent": Decimal("0"),
    "tasks_open": 0,
    "tasks_closed": 0,
    "executor_id": None,
    "executor_full_name": None,
    "executor_tg_id": None,
}


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    return int(value)


def _to_decimal(value: DecimalLike) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def get_deal_kpi_metrics(deal_id: int) -> dict[str, Any]:
    """Return KPI metrics for a deal using a single aggregated query."""

    today = date.today()

    policy_open_case = Case(
        None,
        (
            (
                (Policy.end_date.is_null(True))
                | (Policy.end_date >= today),
                1,
            ),
        ),
        0,
    )
    policy_closed_case = Case(
        None,
        (
            (
                (Policy.end_date.is_null(False))
                & (Policy.end_date < today),
                1,
            ),
        ),
        0,
    )
    policy_metrics = (
        Policy.select(
            Policy.deal_id.alias("deal_id"),
            fn.COALESCE(fn.SUM(policy_open_case), 0).alias("policies_open"),
            fn.COALESCE(fn.SUM(policy_closed_case), 0).alias("policies_closed"),
        )
        .where((Policy.deal_id == deal_id) & (Policy.is_deleted == False))
        .group_by(Policy.deal_id)
        .alias("policy_metrics")
    )

    payment_open_case = Case(
        None,
        ((Payment.actual_payment_date.is_null(True), 1),),
        0,
    )
    payment_closed_case = Case(
        None,
        ((Payment.actual_payment_date.is_null(False), 1),),
        0,
    )
    payment_expected_case = Case(
        None,
        ((Payment.actual_payment_date.is_null(True), Payment.amount),),
        0,
    )
    payment_received_case = Case(
        None,
        ((Payment.actual_payment_date.is_null(False), Payment.amount),),
        0,
    )
    payment_metrics = (
        Payment.select(
            Policy.deal_id.alias("deal_id"),
            fn.COALESCE(fn.SUM(payment_open_case), 0).alias("payments_open"),
            fn.COALESCE(fn.SUM(payment_closed_case), 0).alias("payments_closed"),
            fn.COALESCE(fn.SUM(payment_expected_case), 0).alias("payments_expected"),
            fn.COALESCE(fn.SUM(payment_received_case), 0).alias("payments_received"),
        )
        .join(Policy)
        .where(
            (Policy.deal_id == deal_id)
            & (Policy.is_deleted == False)
            & (Payment.is_deleted == False)
        )
        .group_by(Policy.deal_id)
        .alias("payment_metrics")
    )

    income_open_case = Case(
        None,
        ((Income.received_date.is_null(True), 1),),
        0,
    )
    income_closed_case = Case(
        None,
        ((Income.received_date.is_null(False), 1),),
        0,
    )
    income_expected_case = Case(
        None,
        ((Income.received_date.is_null(True), Income.amount),),
        0,
    )
    income_received_case = Case(
        None,
        ((Income.received_date.is_null(False), Income.amount),),
        0,
    )
    income_metrics = (
        Income.select(
            Policy.deal_id.alias("deal_id"),
            fn.COALESCE(fn.SUM(income_open_case), 0).alias("incomes_open"),
            fn.COALESCE(fn.SUM(income_closed_case), 0).alias("incomes_closed"),
            fn.COALESCE(fn.SUM(income_expected_case), 0).alias("incomes_expected"),
            fn.COALESCE(fn.SUM(income_received_case), 0).alias("incomes_received"),
        )
        .join(Payment)
        .join(Policy)
        .where(
            (Policy.deal_id == deal_id)
            & (Policy.is_deleted == False)
            & (Payment.is_deleted == False)
            & (Income.is_deleted == False)
        )
        .group_by(Policy.deal_id)
        .alias("income_metrics")
    )

    expense_open_case = Case(
        None,
        ((Expense.expense_date.is_null(True), 1),),
        0,
    )
    expense_closed_case = Case(
        None,
        ((Expense.expense_date.is_null(False), 1),),
        0,
    )
    expense_planned_case = Case(
        None,
        ((Expense.expense_date.is_null(True), Expense.amount),),
        0,
    )
    expense_spent_case = Case(
        None,
        ((Expense.expense_date.is_null(False), Expense.amount),),
        0,
    )
    expense_metrics = (
        Expense.select(
            Policy.deal_id.alias("deal_id"),
            fn.COALESCE(fn.SUM(expense_open_case), 0).alias("expenses_open"),
            fn.COALESCE(fn.SUM(expense_closed_case), 0).alias("expenses_closed"),
            fn.COALESCE(fn.SUM(expense_planned_case), 0).alias("expenses_planned"),
            fn.COALESCE(fn.SUM(expense_spent_case), 0).alias("expenses_spent"),
        )
        .join(Payment)
        .join(Policy)
        .where(
            (Policy.deal_id == deal_id)
            & (Policy.is_deleted == False)
            & (Payment.is_deleted == False)
            & (Expense.is_deleted == False)
        )
        .group_by(Policy.deal_id)
        .alias("expense_metrics")
    )

    task_open_case = Case(
        None,
        ((Task.is_done == False, 1),),
        0,
    )
    task_closed_case = Case(
        None,
        ((Task.is_done == True, 1),),
        0,
    )
    task_metrics = (
        Task.select(
            Task.deal_id.alias("deal_id"),
            fn.COALESCE(fn.SUM(task_open_case), 0).alias("tasks_open"),
            fn.COALESCE(fn.SUM(task_closed_case), 0).alias("tasks_closed"),
        )
        .where((Task.deal_id == deal_id) & (Task.is_deleted == False))
        .group_by(Task.deal_id)
        .alias("task_metrics")
    )

    query = (
        Deal.select(
            Deal.id,
            policy_metrics.c.policies_open,
            policy_metrics.c.policies_closed,
            payment_metrics.c.payments_open,
            payment_metrics.c.payments_closed,
            payment_metrics.c.payments_expected,
            payment_metrics.c.payments_received,
            income_metrics.c.incomes_open,
            income_metrics.c.incomes_closed,
            income_metrics.c.incomes_expected,
            income_metrics.c.incomes_received,
            expense_metrics.c.expenses_open,
            expense_metrics.c.expenses_closed,
            expense_metrics.c.expenses_planned,
            expense_metrics.c.expenses_spent,
            task_metrics.c.tasks_open,
            task_metrics.c.tasks_closed,
            Executor.id.alias("executor_id"),
            Executor.full_name.alias("executor_full_name"),
            Executor.tg_id.alias("executor_tg_id"),
        )
        .where(Deal.id == deal_id)
        .join(policy_metrics, JOIN.LEFT_OUTER, on=(policy_metrics.c.deal_id == Deal.id))
        .switch(Deal)
        .join(payment_metrics, JOIN.LEFT_OUTER, on=(payment_metrics.c.deal_id == Deal.id))
        .switch(Deal)
        .join(income_metrics, JOIN.LEFT_OUTER, on=(income_metrics.c.deal_id == Deal.id))
        .switch(Deal)
        .join(expense_metrics, JOIN.LEFT_OUTER, on=(expense_metrics.c.deal_id == Deal.id))
        .switch(Deal)
        .join(task_metrics, JOIN.LEFT_OUTER, on=(task_metrics.c.deal_id == Deal.id))
        .switch(Deal)
        .join(DealExecutor, JOIN.LEFT_OUTER, on=(DealExecutor.deal == Deal.id))
        .join_from(DealExecutor, Executor, JOIN.LEFT_OUTER)
    )

    row = query.dicts().first()
    metrics = DEFAULT_METRICS.copy()
    if not row:
        return metrics

    metrics.update(
        {
            "policies_open": _to_int(row.get("policies_open")),
            "policies_closed": _to_int(row.get("policies_closed")),
            "payments_open": _to_int(row.get("payments_open")),
            "payments_closed": _to_int(row.get("payments_closed")),
            "payments_expected": _to_decimal(row.get("payments_expected")),
            "payments_received": _to_decimal(row.get("payments_received")),
            "incomes_open": _to_int(row.get("incomes_open")),
            "incomes_closed": _to_int(row.get("incomes_closed")),
            "incomes_expected": _to_decimal(row.get("incomes_expected")),
            "incomes_received": _to_decimal(row.get("incomes_received")),
            "expenses_open": _to_int(row.get("expenses_open")),
            "expenses_closed": _to_int(row.get("expenses_closed")),
            "expenses_planned": _to_decimal(row.get("expenses_planned")),
            "expenses_spent": _to_decimal(row.get("expenses_spent")),
            "tasks_open": _to_int(row.get("tasks_open")),
            "tasks_closed": _to_int(row.get("tasks_closed")),
            "executor_id": row.get("executor_id"),
            "executor_full_name": row.get("executor_full_name"),
            "executor_tg_id": row.get("executor_tg_id"),
        }
    )
    return metrics
