import datetime
import json

import pytest
from ui.forms.import_policy_json_form import (
    ImportPolicyJsonForm,
    prepare_policy_payload,
)


def test_prepare_policy_payload_normalizes_dates_and_forced_fields():
    payload = json.dumps(
        {
            "client_name": "Ivan Ivanov",
            "policy": {
                "policy_number": "P1",
                "client_id": 1,
                "deal_id": 2,
            },
            "payments": [
                {
                    "payment_date": "2024-01-10",
                    "actual_payment_date": "2024-01-15",
                    "amount": 100,
                }
            ],
        }
    )

    name, policy, payments = prepare_policy_payload(
        payload,
        forced_client=object(),
        forced_deal=object(),
    )

    assert name == "Ivan Ivanov"
    assert "client_id" not in policy
    assert "deal_id" not in policy
    assert payments[0]["payment_date"] == datetime.date(2024, 1, 10)
    assert payments[0]["actual_payment_date"] == datetime.date(2024, 1, 15)


@pytest.mark.parametrize(
    "payload",
    [
        "{}",
        json.dumps({"client_name": "", "policy": {}, "payments": []}),
        json.dumps({"client_name": "A", "policy": [], "payments": []}),
        json.dumps({"client_name": "A", "policy": {}, "payments": {}}),
        json.dumps({"client_name": "A", "policy": {}, "payments": [{} , "bad"]}),
    ],
)
def test_prepare_policy_payload_invalid_inputs(payload):
    with pytest.raises(ValueError):
        prepare_policy_payload(payload)


def test_import_policy_json_smoke(monkeypatch, qapp):
    class DummyClient:
        name = "C"

    client = DummyClient()
    payload = json.dumps(
        {
            "client_name": "C",
            "policy": {},
            "payments": [
                {
                    "payment_date": "2024-01-10",
                    "amount": 100,
                }
            ],
        }
    )

    class DummyNote:
        def __init__(self):
            self._text = ""

        def text(self):
            return self._text

        def setText(self, value):
            self._text = value

    created_forms = []

    class DummyPolicyForm:
        def __init__(self, *, forced_client, forced_deal, parent, context):
            self.fields = {"note": DummyNote()}
            self._payments = []
            self.saved_instance = None
            self.forced_client = forced_client
            self.forced_deal = forced_deal
            created_forms.append(self)

        def add_payment_row(self, payload):
            self._payments.append(payload)

        def exec(self):
            self.saved_instance = "saved"
            return True

    monkeypatch.setattr(
        "ui.forms.import_policy_json_form.PolicyForm", DummyPolicyForm
    )

    form = ImportPolicyJsonForm(forced_client=client)
    form.text_edit.setPlainText(payload)

    form.on_import_clicked()

    assert form.imported_policy == "saved"
    assert len(created_forms) == 1
    created_form = created_forms[0]
    assert created_form.forced_client == client
    assert created_form.forced_deal is None
    assert created_form.fields["note"].text() == "C"
    assert created_form._payments[0]["payment_date"] == datetime.date(2024, 1, 10)

