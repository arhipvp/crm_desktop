import pytest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from PySide6.QtWidgets import QDialog

from database.models import Client, Policy, Payment, Expense
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
        policy.save()
        return policy

    monkeypatch.setattr(form, "save_data", fake_save_data)
    return form, policy


def test_dialog_creates_expenses_for_selected_payments(policy_form, monkeypatch):
    form, policy = policy_form
    first_payment = Payment.create(
        policy=policy,
        amount=100,
        payment_date=date.today(),
    )
    second_payment = Payment.create(
        policy=policy,
        amount=150,
        payment_date=date.today(),
    )

    from ui.forms import policy_form as module

    created_dialogs: list[tuple[Policy, str]] = []

    class DummyDialog:
        def __init__(self, dlg_policy, contractor_name, parent=None):
            created_dialogs.append((dlg_policy, contractor_name))

        def exec(self) -> int:
            return QDialog.Accepted

        def get_selected_payments(self):
            return [first_payment]

    show_info_mock = MagicMock()
    show_error_mock = MagicMock()
    monkeypatch.setattr(module, "ContractorExpenseDialog", DummyDialog)
    monkeypatch.setattr(module, "show_info", show_info_mock)
    monkeypatch.setattr(module, "show_error", show_error_mock)

    form.save()

    assert created_dialogs == [(policy, "X")]
    show_error_mock.assert_not_called()

    first_expenses = (
        Expense.active()
        .where((Expense.payment == first_payment) & (Expense.expense_type == "контрагент"))
    )
    second_expenses = (
        Expense.active()
        .where((Expense.payment == second_payment) & (Expense.expense_type == "контрагент"))
    )

    assert first_expenses.count() == 1
    assert second_expenses.count() == 0
    show_info_mock.assert_called_once()


def test_no_dialog_when_contractor_unchanged(monkeypatch, qapp, in_memory_db):
    client = Client.create(name="C")
    policy = Policy.create(
        client=client,
        policy_number="P",
        start_date=date.today(),
        end_date=date.today(),
        contractor="X",
    )
    form = PolicyForm(policy)
    monkeypatch.setattr(form, "collect_data", lambda: {"contractor": "X"})
    monkeypatch.setattr(form, "save_data", lambda data: policy)

    from ui.forms import policy_form as module

    dialog_mock = MagicMock()
    show_info_mock = MagicMock()
    monkeypatch.setattr(module, "ContractorExpenseDialog", dialog_mock)
    monkeypatch.setattr(module, "show_info", show_info_mock)

    form.save()

    dialog_mock.assert_not_called()
    show_info_mock.assert_not_called()


def test_no_expense_when_dialog_rejected(policy_form, monkeypatch):
    form, policy = policy_form
    payment = Payment.create(
        policy=policy,
        amount=50,
        payment_date=date.today(),
    )

    from ui.forms import policy_form as module

    class RejectingDialog:
        def __init__(self, *_args, **_kwargs):
            pass

        def exec(self) -> int:
            return QDialog.Rejected

        def get_selected_payments(self):
            return [payment]

    add_expense_mock = MagicMock(return_value=SimpleNamespace(created=[], updated=[]))
    show_info_mock = MagicMock()
    show_error_mock = MagicMock()

    monkeypatch.setattr(module, "ContractorExpenseDialog", RejectingDialog)
    monkeypatch.setattr(module, "add_contractor_expense", add_expense_mock)
    monkeypatch.setattr(module, "show_info", show_info_mock)
    monkeypatch.setattr(module, "show_error", show_error_mock)

    form.save()

    add_expense_mock.assert_not_called()
    show_info_mock.assert_not_called()
    show_error_mock.assert_not_called()


def test_dialog_skipped_for_new_policy(monkeypatch, qapp, in_memory_db):
    client = Client.create(name="C")
    policy = Policy.create(
        client=client,
        policy_number="P",
        start_date=date.today(),
        end_date=date.today(),
        contractor="X",
    )
    Payment.create(policy=policy, amount=0, payment_date=date.today())

    form = PolicyForm()
    monkeypatch.setattr(form, "collect_data", lambda: {"contractor": "X"})
    monkeypatch.setattr(form, "save_data", lambda data: policy)

    from ui.forms import policy_form as module

    dialog_mock = MagicMock()
    monkeypatch.setattr(module, "ContractorExpenseDialog", dialog_mock)
    monkeypatch.setattr(module, "get_expense_count_by_policy", lambda pid: 1)

    form.save()

    dialog_mock.assert_not_called()


def test_add_contractor_expense_creates_record(in_memory_db):
    first_payment_date = date(2024, 1, 1)
    client = Client.create(name="C")
    policy = Policy.create(
        client=client,
        policy_number="P-1",
        start_date=first_payment_date,
        end_date=first_payment_date,
    )
    payment = Payment.create(policy=policy, amount=0, payment_date=first_payment_date)
    policy.contractor = "Контрагент"
    policy.save()

    result = add_contractor_expense(policy)

    assert len(result.created) == 1
    assert not result.updated
    expense = result.created[0]
    assert expense.payment == payment
    assert expense.expense_type == "контрагент"
    assert expense.amount == 0


def test_add_contractor_expense_requires_contractor(in_memory_db):
    first_payment_date = date(2024, 1, 1)
    client = Client.create(name="C")
    policy = Policy.create(
        client=client,
        policy_number="P-1",
        start_date=first_payment_date,
        end_date=first_payment_date,
        contractor="—",
    )
    Payment.create(policy=policy, amount=0, payment_date=first_payment_date)

    with pytest.raises(ValueError):
        add_contractor_expense(policy)


def test_add_contractor_expense_updates_existing_records(in_memory_db):
    payment_date = date(2024, 3, 1)
    actual_date = date(2024, 3, 5)
    client = Client.create(name="C")
    policy = Policy.create(
        client=client,
        policy_number="P-2",
        start_date=payment_date,
        end_date=payment_date,
        contractor="A",
    )
    payment = Payment.create(
        policy=policy,
        amount=Decimal("100"),
        payment_date=payment_date,
        actual_payment_date=actual_date,
    )
    expense = Expense.create(
        payment=payment,
        policy_id=policy.id,
        amount=0,
        expense_type="контрагент",
        note="выплата контрагенту A",
    )

    policy.contractor = "B"
    policy.save()

    result = add_contractor_expense(policy, payments=[payment])

    assert not result.created
    assert len(result.updated) == 1
    updated_expense = Expense.get_by_id(expense.id)
    assert updated_expense.note == "выплата контрагенту B"
    assert updated_expense.expense_date == actual_date


def test_create_expenses_for_all_payments(in_memory_db):
    first_payment_date = date(2024, 1, 1)
    second_payment_date = date(2024, 2, 1)
    client = Client.create(name="C")
    policy = Policy.create(
        client=client,
        policy_number="P-1",
        start_date=first_payment_date,
        end_date=second_payment_date,
    )

    first_payment = Payment.create(policy=policy, amount=100, payment_date=first_payment_date)
    second_payment = Payment.create(policy=policy, amount=200, payment_date=second_payment_date)

    assert Expense.select().count() == 0

    policy.contractor = "Контрагент"
    policy.save()

    result = add_contractor_expense(policy, payments=[first_payment, second_payment])

    assert len(result.created) == 2
    assert not result.updated

    for payment in (first_payment, second_payment):
        contractor_expenses = (
            Expense.active()
            .where(
                (Expense.payment == payment)
                & (Expense.expense_type == "контрагент")
            )
        )
        assert contractor_expenses.count() == 1
