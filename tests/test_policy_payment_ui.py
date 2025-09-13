import datetime
from PySide6.QtCore import QDate

from database.models import Client, Policy, Payment
from ui.forms.policy_form import PolicyForm
from ui.forms.policy_merge_dialog import PolicyMergeDialog
from services.policies import policy_service as policy_svc


def test_policy_form_sets_actual_payment_date(
    in_memory_db, mock_payments, policy_folder_patches, qapp
):
    client = Client.create(name="C")
    form = PolicyForm(forced_client=client)
    form.policy_number_edit.setText("P")
    form.fields["start_date"].setDate(QDate(2024, 1, 1))
    form.fields["end_date"].setDate(QDate(2024, 2, 1))
    form.pay_date_edit.setDate(QDate(2024, 1, 10))
    form.pay_amount_edit.setText("100")
    form.on_add_payment()
    chk = form.payments_table.cellWidget(0, 2)
    chk.setChecked(True)
    form.save()
    payment = Payment.get()
    assert payment.actual_payment_date == payment.payment_date


def test_policy_merge_dialog_sets_actual_payment_date(
    in_memory_db, mock_payments, policy_folder_patches, qapp
):
    d1 = datetime.date(2024, 1, 1)
    d2 = datetime.date(2024, 2, 1)
    client = Client.create(name="C")
    policy = Policy.create(client=client, policy_number="P", start_date=d1, end_date=d2)
    Payment.create(policy=policy, amount=100, payment_date=d1)
    dlg = PolicyMergeDialog(policy, {})
    chk = dlg.payments_table.cellWidget(0, 2)
    chk.setChecked(True)
    payments = dlg.get_merged_payments()
    policy_svc.update_policy(
        policy,
        payments=payments,
        first_payment_paid=dlg.first_payment_checkbox.isChecked(),
    )
    p = Payment.get()
    assert p.actual_payment_date == p.payment_date
