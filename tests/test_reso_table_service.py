import pandas as pd
import types
from services.reso_table_service import load_reso_table, import_reso_payouts, COLUMNS


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


def test_import_reso_payouts_unique(monkeypatch):
    df = pd.DataFrame({"НОМЕР ПОЛИСА": ["A", "A", "B"], "arhvp": ["10", "10", "20"]})
    monkeypatch.setattr("services.reso_table_service.load_reso_table", lambda p: df)

    events = {"pol": 0, "inc": 0, "amounts": []}

    class DummyField:
        def setText(self, val):
            events["amounts"].append(val)

    class FakePolicyForm:
        def __init__(self, parent=None):
            self.fields = {"policy_number": DummyField()}

        def exec(self):
            events["pol"] += 1
            self.saved_instance = types.SimpleNamespace(
                deal_id=None,
                payments=types.SimpleNamespace(order_by=lambda *_: types.SimpleNamespace(first=lambda: types.SimpleNamespace(id=1)))
            )
            return True

    class FakeIncomeForm:
        def __init__(self, parent=None, deal_id=None):
            self.fields = {"amount": DummyField()}

        def prefill_payment(self, pid):
            pass

        def exec(self):
            events["inc"] += 1
            return True

    count = import_reso_payouts("dummy", policy_form_cls=FakePolicyForm, income_form_cls=FakeIncomeForm)
    assert count == 2
    assert events["pol"] == 2
    assert events["inc"] == 2
    assert events["amounts"] == ["A", "10", "B", "20"]
