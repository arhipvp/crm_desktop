from datetime import date

from services.client_service import add_client
from services.deal_service import add_deal, update_deal, mark_deal_deleted, get_deal_by_id
from services.policy_service import add_policy, update_policy, prolong_policy, get_unique_policy_field_values
from services.payment_service import add_payment, update_payment, mark_payment_deleted
from services.income_service import add_income, update_income, mark_income_deleted
from services.expense_service import add_expense, update_expense, mark_expense_deleted
from database.models import Payment, Income, Expense, Policy


def test_update_deal_and_mark_deleted(monkeypatch):
    client = add_client(name="Upd")
    monkeypatch.setattr(
        "services.deal_service.create_deal_folder",
        lambda *a, **k: ("/tmp/deal", "link"),
    )
    deal = add_deal(client_id=client.id, start_date="2025-01-01", description="D")
    update_deal(
        deal,
        journal_entry="note",
        is_closed=True,
        closed_reason="ok",
    )
    assert "Сделка закрыта" in deal.calculations
    assert "note" in deal.calculations
    mark_deal_deleted(deal.id)
    assert get_deal_by_id(deal.id) is None


def test_update_payment_and_delete(monkeypatch):
    client = add_client(name="Pay")
    policy = add_policy(
        client_id=client.id,
        policy_number="P1",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        open_folder=lambda *_: None,
    )
    payment = add_payment(policy_id=policy.id, amount=10, payment_date=date(2025, 1, 1))
    update_payment(payment, amount=20)
    assert payment.amount == 20
    mark_payment_deleted(payment.id)
    assert Payment.get_by_id(payment.id).is_deleted


def test_update_income_and_expense(monkeypatch):
    client = add_client(name="Inc")
    policy = add_policy(
        client_id=client.id,
        policy_number="I1",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        open_folder=lambda *_: None,
    )
    payment = add_payment(policy_id=policy.id, amount=100, payment_date=date(2025, 1, 2))
    income = add_income(payment_id=payment.id, amount=50)
    update_income(income, amount=60, received_date=date(2025, 1, 3))
    assert income.amount == 60
    mark_income_deleted(income.id)
    assert Income.get_by_id(income.id).is_deleted
    expense = add_expense(payment_id=payment.id, amount=30, expense_type="agent")
    update_expense(expense, amount=40)
    assert expense.amount == 40
    mark_expense_deleted(expense.id)
    assert Expense.get_by_id(expense.id).is_deleted


def test_update_and_prolong_policy(monkeypatch):
    client = add_client(name="Pol")
    policy = add_policy(
        client_id=client.id,
        policy_number="PP1",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        open_folder=lambda *_: None,
    )
    update_policy(policy, note="upd")
    assert policy.note == "upd"

    def fake_create(**kw):
        obj = Policy(**kw)
        obj.id = 999
        return obj

    monkeypatch.setattr("services.policy_service.Policy.create", staticmethod(fake_create))
    monkeypatch.setattr("services.policy_service.Policy.save", lambda self: None)
    new_policy = prolong_policy(policy)
    assert new_policy.start_date > policy.start_date
    values = get_unique_policy_field_values("insurance_company")
    assert isinstance(values, list)
