import json
import datetime
from PySide6.QtWidgets import QDialog

from database.models import Client, Payment, Policy
from ui.forms.import_policy_json_form import ImportPolicyJsonForm
from ui.forms.policy_form import PolicyForm


def test_import_policy_json_with_payments_creates_records(
    in_memory_db, mock_payments, policy_folder_patches, qapp, monkeypatch
):
    client = Client.create(name="C")
    data = {
        "client_name": "C",
        "policy": {
            "policy_number": "P1",
            "start_date": "2024-01-01",
            "end_date": "2024-02-01",
        },
        "payments": [
            {
                "payment_date": "2024-01-10",
                "amount": 100,
                "actual_payment_date": "2024-01-15",
            },
            {
                "payment_date": "2024-02-10",
                "amount": 200,
                "actual_payment_date": "2024-02-15",
            },
        ],
    }

    form = ImportPolicyJsonForm(forced_client=client)
    form.text_edit.setPlainText(json.dumps(data))

    def fake_exec(self):
        self.save()
        return QDialog.Accepted

    monkeypatch.setattr(PolicyForm, "exec", fake_exec)

    form.on_import_clicked()

    policy = Policy.get()
    payments = list(policy.payments.order_by(Payment.payment_date))
    assert [float(p.amount) for p in payments] == [100.0, 200.0]
    assert [p.payment_date for p in payments] == [
        datetime.date(2024, 1, 10),
        datetime.date(2024, 2, 10),
    ]
    assert [p.actual_payment_date for p in payments] == [
        datetime.date(2024, 1, 15),
        datetime.date(2024, 2, 15),
    ]
