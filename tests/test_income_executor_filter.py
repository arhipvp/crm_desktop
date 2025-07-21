from datetime import date
from peewee import prefetch
import pytest
from services.client_service import add_client
from services.deal_service import add_deal
from services.executor_service import add_executor, assign_executor
from services.policy_service import add_policy
from services.payment_service import add_payment
from services.income_service import add_income, get_incomes_page
from database.models import Executor, Payment, Policy, Client, Deal, DealExecutor


def test_income_filter_by_executor(test_db):
    client = add_client(name='X')
    add_executor(full_name='Executor 55', tg_id=55)
    deal = add_deal(client_id=client.id, start_date=date(2025, 1, 1), description='D')
    assign_executor(deal.id, 55)
    policy = add_policy(client_id=client.id, deal_id=deal.id, policy_number='P1', start_date=date(2025,1,1), end_date=date(2025,12,31))
    pay = add_payment(policy_id=policy.id, amount=10, payment_date=date(2025,1,2))
    inc = add_income(payment_id=pay.id, amount=5, received_date=date(2025,1,3))

    query = get_incomes_page(1, 10, column_filters={Executor.full_name: '55'})
    items = list(prefetch(query, Payment, Policy, Client, Deal, DealExecutor, Executor))
    assert inc in items
