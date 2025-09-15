import pytest
from unittest.mock import MagicMock

from database.models import Client, Policy
from datetime import date
from ui.forms.policy_form import PolicyForm


@pytest.fixture
def policy_form(monkeypatch, qapp, in_memory_db):
    client = Client.create(name="C")
    policy = Policy.create(
        client=client,
        policy_number="P",
        start_date=date.today(),
        end_date=date.today(),
    )
    form = PolicyForm(policy)
    monkeypatch.setattr(form, "collect_data", lambda: {"contractor": "X"})
    monkeypatch.setattr(form, "save_data", lambda data: policy)
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
