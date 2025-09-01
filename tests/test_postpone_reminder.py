from datetime import date as real_date, timedelta

from ui.views.deal_detail import tabs
from ui.views.deal_detail.tabs import DealTabsMixin
from PySide6.QtCore import QDate


class DummyDateEdit:
    def __init__(self):
        self._date = None

    def setDate(self, qdate: QDate):
        self._date = qdate


class DummyDeal(DealTabsMixin):
    def __init__(self):
        self.reminder_date = DummyDateEdit()
        self.saved = False

    def _on_save_and_close(self):
        self.saved = True


def test_postpone_reminder_uses_today(monkeypatch):
    class FixedDate(real_date):
        @classmethod
        def today(cls):
            return cls(2024, 4, 8)

    monkeypatch.setattr(tabs, "date", FixedDate)

    deal = DummyDeal()
    deal._postpone_reminder(2)

    assert deal.reminder_date._date.toPython() == FixedDate.today() + timedelta(days=2)
    assert deal.saved
