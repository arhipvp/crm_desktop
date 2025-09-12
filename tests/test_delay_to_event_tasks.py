from datetime import date, timedelta

import pytest
from PySide6.QtCore import QDate

from database.models import Client, Deal, Task
from ui.views.deal_detail import tabs
from ui.views.deal_detail.actions import DealActionsMixin
from ui.views.deal_detail.tabs import DealTabsMixin


class DummyView(DealActionsMixin):
    def __init__(self, deal):
        self.instance = deal
        self.tabs_inited = False

    def _collect_upcoming_events(self):
        return [("Event", date.today())]

    def _init_tabs(self):
        self.tabs_inited = True

    def accept(self):
        pass


class DummyDialog:
    def __init__(self, events, parent=None):
        pass

    def exec(self):
        return True

    def get_reminder_date(self):
        return date.today()


@pytest.mark.usefixtures("in_memory_db")
@pytest.mark.parametrize(
    "confirm_result, closed_count",
    [
        (True, 2),
        (False, 0),
    ],
)
def test_tasks_closed_depends_on_confirm(
    monkeypatch, confirm_result, closed_count
):
    from ui.forms import deal_next_event_dialog

    monkeypatch.setattr(
        deal_next_event_dialog, "DealNextEventDialog", DummyDialog
    )
    monkeypatch.setattr(
        "ui.views.deal_detail.actions.confirm",
        lambda *a, **k: confirm_result,
    )

    client = Client.create(name="C")
    deal = Deal.create(client=client, description="D", start_date=date.today())
    Task.create(title="T1", due_date=date.today(), deal=deal)
    Task.create(title="T2", due_date=date.today(), deal=deal)

    view = DummyView(deal)
    view._on_delay_to_event()

    assert Task.select().where(Task.is_done == True).count() == closed_count
    assert view.tabs_inited == confirm_result


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
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2024, 4, 8)

    monkeypatch.setattr(tabs, "date", FixedDate)

    deal = DummyDeal()
    deal._postpone_reminder(2)

    assert deal.reminder_date._date.toPython() == FixedDate.today() + timedelta(days=2)
    assert deal.saved

