from datetime import date

from database.models import Client, Deal, Policy, Payment, Expense
from services.expense_service import build_expense_query


def test_apply_expense_filters_field_keys(in_memory_db):
    client = Client.create(name="C1")
    deal1 = Deal.create(client=client, description="D1", start_date=date.today())
    deal2 = Deal.create(client=client, description="D2", start_date=date.today())
    policy1 = Policy.create(
        client=client, deal=deal1, policy_number="P1", start_date=date.today()
    )
    policy2 = Policy.create(
        client=client, deal=deal2, policy_number="P2", start_date=date.today()
    )
    payment1 = Payment.create(policy=policy1, amount=100, payment_date=date.today())
    payment2 = Payment.create(policy=policy2, amount=200, payment_date=date.today())
    Expense.create(payment=payment1, amount=10, expense_type="t1", policy=policy1)
    Expense.create(payment=payment2, amount=20, expense_type="t1", policy=policy2)

    query = build_expense_query(column_filters={Deal.description: "D1"})
    results = list(query)
    assert len(results) == 1
    assert results[0].policy.policy_number == "P1"
