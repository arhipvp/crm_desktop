import pytest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from PySide6.QtWidgets import QDialog

from database.models import Client, Policy, Payment, Expense
from services.policies import add_contractor_expense, add_policy
from ui.forms import policy_form as policy_form_module
from ui.forms.policy_form import PolicyForm, handle_contractor_expense_dialog


def test_add_policy_first_payment_paid_sets_contractor_expense_date(
    in_memory_db, policy_folder_patches
):
    client = Client.create(name="Client")
    start_date = date(2024, 1, 1)

    policy = add_policy(
        client=client,
        policy_number="P-NEW",
        start_date=start_date,
        end_date=start_date,
        contractor="Контрагент",
        first_payment_paid=True,
    )

    payment = (
        Payment.active()
        .where(Payment.policy == policy)
        .order_by(Payment.payment_date)
        .first()
    )
    assert payment is not None
    assert payment.actual_payment_date == payment.payment_date

    expense = (
        Expense.active()
        .where(
            (Expense.payment == payment)
            & (Expense.expense_type == "контрагент")
        )
        .first()
    )
    assert expense is not None
    assert expense.expense_date is None


def test_handle_dialog_creates_expenses_for_selected_payments():
    previous_policy = SimpleNamespace(contractor="Y")
    saved_policy = SimpleNamespace(id=1, contractor="X")
    selected_payments = [SimpleNamespace(id=10)]
    created_dialogs = []
    parent_token = object()

    class DummyDialog:
        def __init__(self, dlg_policy, contractor_name, parent=None):
            created_dialogs.append((dlg_policy, contractor_name, parent))

        def exec(self) -> int:
            return QDialog.Accepted

        def get_selected_payments(self):
            return selected_payments

    add_expense_result = SimpleNamespace(created=["expense"], updated=[])
    add_expense_mock = MagicMock(return_value=add_expense_result)
    show_info_mock = MagicMock()
    show_error_mock = MagicMock()

    result = handle_contractor_expense_dialog(
        previous_policy,
        saved_policy,
        parent=parent_token,
        get_expense_count_by_policy=lambda _pid: 0,
        contractor_dialog_factory=DummyDialog,
        add_contractor_expense=add_expense_mock,
        show_info=show_info_mock,
        show_error=show_error_mock,
    )

    assert len(created_dialogs) == 1
    dlg_policy, contractor_name, parent = created_dialogs[0]
    assert dlg_policy is saved_policy
    assert contractor_name == "X"
    assert parent is parent_token
    assert result.contractor_changed is True
    assert result.dialog_shown is True
    assert result.expenses_created == ["expense"]
    assert result.expenses_updated == []
    add_expense_mock.assert_called_once_with(saved_policy, payments=selected_payments)
    show_info_mock.assert_called_once_with("Расходы для контрагента созданы.")
    show_error_mock.assert_not_called()


def test_handle_dialog_skips_when_contractor_unchanged():
    previous_policy = SimpleNamespace(contractor="X")
    saved_policy = SimpleNamespace(id=1, contractor="X")
    get_count_mock = MagicMock(return_value=0)
    dialog_factory = MagicMock()
    add_expense_mock = MagicMock()
    show_info_mock = MagicMock()
    show_error_mock = MagicMock()

    result = handle_contractor_expense_dialog(
        previous_policy,
        saved_policy,
        parent=None,
        get_expense_count_by_policy=get_count_mock,
        contractor_dialog_factory=dialog_factory,
        add_contractor_expense=add_expense_mock,
        show_info=show_info_mock,
        show_error=show_error_mock,
    )

    assert result.contractor_changed is False
    assert result.dialog_shown is False
    get_count_mock.assert_not_called()
    dialog_factory.assert_not_called()
    add_expense_mock.assert_not_called()
    show_info_mock.assert_not_called()
    show_error_mock.assert_not_called()


def test_handle_dialog_no_expense_when_rejected():
    previous_policy = SimpleNamespace(contractor="Y")
    saved_policy = SimpleNamespace(id=2, contractor="X")

    class RejectingDialog:
        def __init__(self, *_args, **_kwargs):
            pass

        def exec(self) -> int:
            return QDialog.Rejected

        def get_selected_payments(self):
            return [SimpleNamespace(id=1)]

    add_expense_mock = MagicMock()
    show_info_mock = MagicMock()
    show_error_mock = MagicMock()

    result = handle_contractor_expense_dialog(
        previous_policy,
        saved_policy,
        parent=None,
        get_expense_count_by_policy=lambda _pid: 0,
        contractor_dialog_factory=RejectingDialog,
        add_contractor_expense=add_expense_mock,
        show_info=show_info_mock,
        show_error=show_error_mock,
    )

    assert result.contractor_changed is True
    assert result.dialog_shown is True
    assert result.expenses_created == []
    assert result.expenses_updated == []
    add_expense_mock.assert_not_called()
    show_info_mock.assert_not_called()
    show_error_mock.assert_not_called()


def test_handle_dialog_skipped_for_new_policy_with_existing_expenses():
    saved_policy = SimpleNamespace(id=5, contractor="X")
    dialog_factory = MagicMock()

    result = handle_contractor_expense_dialog(
        None,
        saved_policy,
        parent=None,
        get_expense_count_by_policy=lambda _pid: 1,
        contractor_dialog_factory=dialog_factory,
        add_contractor_expense=MagicMock(),
        show_info=MagicMock(),
        show_error=MagicMock(),
    )

    assert result.contractor_changed is True
    assert result.dialog_shown is False
    dialog_factory.assert_not_called()


def test_policy_form_save_invokes_helper(monkeypatch, qapp, in_memory_db):
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
        policy.contractor = data["contractor"]
        policy.save()
        return policy

    monkeypatch.setattr(form, "save_data", fake_save_data)

    helper_result = SimpleNamespace(
        contractor_changed=True,
        dialog_shown=False,
        expenses_created=[],
        expenses_updated=[],
    )
    helper_mock = MagicMock(return_value=helper_result)
    monkeypatch.setattr(policy_form_module, "handle_contractor_expense_dialog", helper_mock)

    form.save()

    helper_mock.assert_called_once()
    args, kwargs = helper_mock.call_args
    assert args == (policy, policy)
    assert kwargs["parent"] is form
    assert kwargs["get_expense_count_by_policy"] is policy_form_module.get_expense_count_by_policy
    assert kwargs["contractor_dialog_factory"] is policy_form_module.ContractorExpenseDialog
    assert kwargs["add_contractor_expense"] is policy_form_module.add_contractor_expense
    assert kwargs["show_info"] is policy_form_module.show_info
    assert kwargs["show_error"] is policy_form_module.show_error


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
    assert updated_expense.expense_date is None


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
