import pytest
from unittest.mock import MagicMock

from database.models import Client, Policy, Payment, Expense
from datetime import date
from ui.forms.policy_form import PolicyForm
from services.policies import add_contractor_expense


@pytest.fixture
def policy_form(monkeypatch, qapp, in_memory_db):
    client = Client.create(name="C")
    policy = Policy.create(
        client=client,
        policy_number="P",
        start_date=date.today(),
        end_date=date.today(),
        contractor="Y",
    )
    form = PolicyForm(policy)
    monkeypatch.setattr(form, "collect_data", lambda: {"contractor": "X"})
    def fake_save_data(data):
        policy.contractor = data.get("contractor")
        return policy
    monkeypatch.setattr(form, "save_data", fake_save_data)
    return form, policy


def test_expense_created_on_confirm(policy_form, monkeypatch):
    form, policy = policy_form
    from ui.forms import policy_form as module

    confirm_mock = MagicMock(return_value=True)
    show_info_mock = MagicMock()
    add_expense_mock = MagicMock()

    monkeypatch.setattr(module, "confirm", confirm_mock)
    monkeypatch.setattr(module, "show_info", show_info_mock)
    monkeypatch.setattr(module, "add_contractor_expense", add_expense_mock)
    monkeypatch.setattr(module, "get_expense_count_by_policy", lambda pid: 0)

    form.save()

    assert confirm_mock.call_count == 1
    add_expense_mock.assert_called_once_with(policy)
    show_info_mock.assert_called_once()


def test_expense_created_when_previous_contractor_invalid(monkeypatch, qapp, in_memory_db):
    client = Client.create(name="C")
    policy = Policy.create(
        client=client,
        policy_number="P",
        start_date=date.today(),
        end_date=date.today(),
        contractor="-",
    )
    form = PolicyForm(policy)

    from ui.forms import policy_form as module

    confirm_mock = MagicMock(return_value=True)
    show_info_mock = MagicMock()
    add_expense_mock = MagicMock()

    monkeypatch.setattr(form, "collect_data", lambda: {"contractor": "X"})
    def fake_save_data(data):
        policy.contractor = data.get("contractor")
        return policy
    monkeypatch.setattr(form, "save_data", fake_save_data)
    monkeypatch.setattr(module, "confirm", confirm_mock)
    monkeypatch.setattr(module, "show_info", show_info_mock)
    monkeypatch.setattr(module, "add_contractor_expense", add_expense_mock)
    monkeypatch.setattr(module, "get_expense_count_by_policy", lambda pid: 0)

    form.save()

    confirm_mock.assert_called_once()
    add_expense_mock.assert_called_once_with(policy)
    show_info_mock.assert_called_once()


def test_no_confirm_when_contractor_unchanged(monkeypatch, qapp, in_memory_db):
    client = Client.create(name="C")
    policy = Policy.create(
        client=client,
        policy_number="P",
        start_date=date.today(),
        end_date=date.today(),
        contractor="X",
    )
    form = PolicyForm(policy)

    from ui.forms import policy_form as module

    confirm_mock = MagicMock(return_value=True)
    show_info_mock = MagicMock()
    add_expense_mock = MagicMock()

    monkeypatch.setattr(form, "collect_data", lambda: {"contractor": "X"})
    monkeypatch.setattr(form, "save_data", lambda data: policy)
    monkeypatch.setattr(module, "confirm", confirm_mock)
    monkeypatch.setattr(module, "show_info", show_info_mock)
    monkeypatch.setattr(module, "add_contractor_expense", add_expense_mock)
    monkeypatch.setattr(module, "get_expense_count_by_policy", lambda pid: 0)

    form.save()

    confirm_mock.assert_not_called()
    add_expense_mock.assert_not_called()
    show_info_mock.assert_not_called()


def test_expense_not_created_on_cancel(policy_form, monkeypatch):
    form, _ = policy_form
    from ui.forms import policy_form as module

    confirm_mock = MagicMock(return_value=False)
    show_info_mock = MagicMock()
    add_expense_mock = MagicMock()

    monkeypatch.setattr(module, "confirm", confirm_mock)
    monkeypatch.setattr(module, "show_info", show_info_mock)
    monkeypatch.setattr(module, "add_contractor_expense", add_expense_mock)
    monkeypatch.setattr(module, "get_expense_count_by_policy", lambda pid: 0)

    form.save()

    confirm_mock.assert_called_once()
    add_expense_mock.assert_not_called()
    show_info_mock.assert_not_called()


def test_second_dialog_shown_when_expenses_exist(policy_form, monkeypatch):
    form, policy = policy_form
    from ui.forms import policy_form as module

    confirm_mock = MagicMock(side_effect=[True, True])
    show_info_mock = MagicMock()
    add_expense_mock = MagicMock()

    monkeypatch.setattr(module, "confirm", confirm_mock)
    monkeypatch.setattr(module, "show_info", show_info_mock)
    monkeypatch.setattr(module, "add_contractor_expense", add_expense_mock)
    monkeypatch.setattr(module, "get_expense_count_by_policy", lambda pid: 1)

    form.save()

    assert confirm_mock.call_count == 2
    add_expense_mock.assert_called_once_with(policy)
    show_info_mock.assert_called_once()


def test_expense_created_for_new_policy(monkeypatch, qapp, in_memory_db):
    client = Client.create(name="C")
    policy = Policy.create(
        client=client,
        policy_number="P",
        start_date=date.today(),
        end_date=date.today(),
        contractor="X",
    )
    form = PolicyForm()
    monkeypatch.setattr(form, "collect_data", lambda: {"contractor": "X"})
    monkeypatch.setattr(form, "save_data", lambda data: policy)
    from ui.forms import policy_form as module

    confirm_mock = MagicMock(return_value=True)
    show_info_mock = MagicMock()
    add_expense_mock = MagicMock()

    monkeypatch.setattr(module, "confirm", confirm_mock)
    monkeypatch.setattr(module, "show_info", show_info_mock)
    monkeypatch.setattr(module, "add_contractor_expense", add_expense_mock)
    monkeypatch.setattr(module, "get_expense_count_by_policy", lambda pid: 0)

    form.save()

    assert confirm_mock.call_count == 1
    add_expense_mock.assert_called_once_with(policy)
    show_info_mock.assert_called_once()


def test_create_expenses_for_all_payments(in_memory_db):
    first_payment_date = date(2024, 1, 1)
    second_payment_date = date(2024, 2, 1)
    client = Client.create(name="C")
    policy = Policy.create(
        client=client,
        policy_number="P-1",
        start_date=first_payment_date,
        end_date=second_payment_date,
        contractor=None,
    )

    p1 = Payment.create(policy=policy, amount=100, payment_date=first_payment_date)
    p2 = Payment.create(policy=policy, amount=200, payment_date=second_payment_date)

    assert Expense.select().count() == 0

    policy.contractor = "Контрагент"
    policy.save()

    created_expenses = add_contractor_expense(policy)

    assert len(created_expenses) == 2
    assert all(expense.amount == 0 for expense in created_expenses)

    for payment in (p1, p2):
        contractor_expenses = (
            Expense.active()
            .where(
                (Expense.payment == payment)
                & (Expense.expense_type == "контрагент")
            )
        )
        assert contractor_expenses.count() == 1
