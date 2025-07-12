import pandas as pd
import types
from datetime import date
from services.reso_table_service import (
    load_reso_table,
    import_reso_payouts,
    COLUMNS,
)
from services.client_service import add_client
from services.policy_service import add_policy
from database.models import Payment, Income


def test_load_reso_table(tmp_path):
    data = (
        "\t".join(COLUMNS) + "\n" +
        "\t".join([
            "АГЕНТСТВО 007",
            "МАРЬИНСКИХ ЮЛИЯ АЛЕКСЕЕВНА [75736]",
            "09.07.2025",
            "Комиссия",
            "SYS2831779653",
            "2831779653",
            "КОТЕЛЬНИКОВ КИРИЛЛ ВЛАДИМИРОВИЧ [66772980]",
            "30.06.2025 -29.06.2026",
            "13100",
            "29.1",
            "3814.41",
            "14860.03",
            "16.06.2025",
            "КОМИССИЯ, Полис SYS2831779653, Начисление: с 30.06.2025 по 29.06.2026, Бордеро №10292091 от 16.06.2025",
            "10292091",
            "16.06.2025",
            "Марьинских Юлия Алексеевна",
            "HOUSEUS3",
            "-",
            "Марьинских Юлия Алексеевна [75736]",
            "Мой",
            "",
            "3394.8249",
            "",
            "",
            ""
        ])
    )
    file = tmp_path / "table.tsv"
    file.write_text(data, encoding="utf-8")

    df = load_reso_table(file)
    assert list(df.columns) == COLUMNS
    assert df.iloc[0]["АГЕНТСТВО"] == "АГЕНТСТВО 007"
    assert df.shape == (1, len(COLUMNS))


def test_import_reso_payout_new_policy(monkeypatch):
    df = pd.DataFrame(
        {
            "НОМЕР ПОЛИСА": ["A"],
            "НАЧИСЛЕНИЕ,С-ПО": ["01.01.2025 -31.12.2025"],
            "arhvp": ["10"],
        }
    )
    monkeypatch.setattr("services.reso_table_service.load_reso_table", lambda p: df)

    events = {"sel": 0, "prev": 0, "pol": 0, "inc": 0, "amount": None}

    def select_policy(df, col, parent=None):
        events["sel"] += 1
        return df.iloc[0]

    class DummyField:
        def setText(self, val):
            events["amount"] = val

        def setDate(self, val):
            pass

    class FakePreview:
        def __init__(self, data, parent=None):
            events["prev"] += 1

        def exec(self):
            return True

    class FakePolicyForm:
        def __init__(self, parent=None):
            self.fields = {
                "policy_number": DummyField(),
                "start_date": DummyField(),
                "end_date": DummyField(),
            }

        def exec(self):
            events["pol"] += 1
            self.saved_instance = types.SimpleNamespace(
                deal_id=None,
                payments=types.SimpleNamespace(
                    order_by=lambda *_: types.SimpleNamespace(
                        first=lambda: types.SimpleNamespace(id=1)
                    )
                ),
            )
            return True

    class FakeIncomeForm:
        def __init__(self, parent=None, deal_id=None):
            events["inc"] += 1
            self.fields = {"amount": DummyField()}

        def prefill_payment(self, pid):
            pass

        def exec(self):
            return True

    class FakeMapDlg:
        def __init__(self, columns, parent=None):
            pass

        def exec(self):
            return True

        def get_mapping(self):
            return {"policy_number": "НОМЕР ПОЛИСА", "period": "НАЧИСЛЕНИЕ,С-ПО", "amount": "arhvp"}

    def select_policy(df, col, parent=None):
        events["sel"] += 1
        return df.iloc[0]

    count = import_reso_payouts(
        "dummy",
        select_policy_func=select_policy,
        column_map_cls=FakeMapDlg,
        preview_cls=FakePreview,
        policy_form_cls=FakePolicyForm,
        income_form_cls=FakeIncomeForm,
    )
    assert count == 1
    assert events == {"sel": 1, "prev": 1, "pol": 1, "inc": 1, "amount": "10"}


def test_import_reso_payout_existing_policy(monkeypatch):
    client = add_client(name="C")
    policy = add_policy(
        client_id=client.id,
        policy_number="A",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )

    df = pd.DataFrame(
        {
            "НОМЕР ПОЛИСА": ["A"],
            "НАЧИСЛЕНИЕ,С-ПО": ["01.01.2025 -31.12.2025"],
            "arhvp": ["15"],
        }
    )
    monkeypatch.setattr("services.reso_table_service.load_reso_table", lambda p: df)

    events = {"sel": 0, "prev": 0, "pol": 0, "inc": 0}

    def select_policy(df, col, parent=None):
        events["sel"] += 1
        return df.iloc[0]

    class FakePreview:
        def __init__(self, data, parent=None):
            events["prev"] += 1

        def exec(self):
            return True

    class FakePolicyForm:
        def __init__(self, parent=None):
            events["pol"] += 1
            self.fields = {}

        def exec(self):
            return True

    class FakeIncomeForm:
        def __init__(self, instance=None, parent=None, deal_id=None):
            events["inc"] += 1
            self.fields = {}

        def prefill_payment(self, pid):
            pass

        def exec(self):
            return True

    class FakeMapDlg:
        def __init__(self, columns, parent=None):
            pass

        def exec(self):
            return True

        def get_mapping(self):
            return {"policy_number": "НОМЕР ПОЛИСА", "period": "НАЧИСЛЕНИЕ,С-ПО", "amount": "arhvp"}

    def select_policy(df, col, parent=None):
        events["sel"] += 1
        return df.iloc[0]

    count = import_reso_payouts(
        "dummy",
        select_policy_func=select_policy,
        column_map_cls=FakeMapDlg,
        preview_cls=FakePreview,
        policy_form_cls=FakePolicyForm,
        income_form_cls=FakeIncomeForm,
    )
    assert count == 1
    assert events == {"sel": 1, "prev": 1, "pol": 0, "inc": 1}


def test_import_reso_payout_updates_pending_income(monkeypatch):
    client = add_client(name="X")
    policy = add_policy(
        client_id=client.id,
        policy_number="B",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    payment = policy.payments.order_by(Payment.id).first()
    pending_inc = payment.incomes.order_by(Income.id).first()

    df = pd.DataFrame(
        {
            "НОМЕР ПОЛИСА": ["B"],
            "НАЧИСЛЕНИЕ,С-ПО": ["01.01.2025 -31.12.2025"],
            "arhvp": ["7"],
        }
    )
    monkeypatch.setattr("services.reso_table_service.load_reso_table", lambda p: df)

    events = {"sel": 0, "prev": 0, "inst": None, "amount": None, "pol": 0}

    def select_policy(df, col, parent=None):
        events["sel"] += 1
        return df.iloc[0]

    class FakePreview:
        def __init__(self, data, parent=None):
            events["prev"] += 1

        def exec(self):
            return True

    class FakePolicyForm:
        def __init__(self, parent=None):
            events["pol"] += 1
            self.fields = {}

        def exec(self):
            return True

    class DummyField:
        def setText(self, val):
            events["amount"] = val

    class FakeIncomeForm:
        def __init__(self, instance=None, parent=None, deal_id=None):
            events["inst"] = instance
            self.fields = {"amount": DummyField()}

        def prefill_payment(self, pid):
            events.setdefault("prefill", pid)

        def exec(self):
            return True

    class FakeMapDlg:
        def __init__(self, columns, parent=None):
            pass

        def exec(self):
            return True

        def get_mapping(self):
            return {"policy_number": "НОМЕР ПОЛИСА", "period": "НАЧИСЛЕНИЕ,С-ПО", "amount": "arhvp"}

    count = import_reso_payouts(
        "dummy",
        select_policy_func=select_policy,
        column_map_cls=FakeMapDlg,
        preview_cls=FakePreview,
        policy_form_cls=FakePolicyForm,
        income_form_cls=FakeIncomeForm,
    )
    assert count == 1
    assert events["pol"] == 0
    assert events["inst"] == pending_inc
    assert events["amount"] == "7"

