from datetime import date

import pytest

from database.models import Client, Deal, Task
from ui.views.deal_detail.actions import DealActionsMixin


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
def test_tasks_closed_on_confirm(monkeypatch):
    from ui.forms import deal_next_event_dialog

    monkeypatch.setattr(
        deal_next_event_dialog, "DealNextEventDialog", DummyDialog
    )
    monkeypatch.setattr(
        "ui.views.deal_detail.actions.confirm", lambda *a, **k: True
    )

    client = Client.create(name="C")
    deal = Deal.create(client=client, description="D", start_date=date.today())
    Task.create(title="T1", due_date=date.today(), deal=deal)
    Task.create(title="T2", due_date=date.today(), deal=deal)

    view = DummyView(deal)
    view._on_delay_to_event()

    assert Task.select().where(Task.is_done == True).count() == 2
    assert view.tabs_inited


@pytest.mark.usefixtures("in_memory_db")
def test_tasks_not_closed_on_decline(monkeypatch):
    from ui.forms import deal_next_event_dialog

    monkeypatch.setattr(
        deal_next_event_dialog, "DealNextEventDialog", DummyDialog
    )
    monkeypatch.setattr(
        "ui.views.deal_detail.actions.confirm", lambda *a, **k: False
    )

    client = Client.create(name="C")
    deal = Deal.create(client=client, description="D", start_date=date.today())
    Task.create(title="T1", due_date=date.today(), deal=deal)

    view = DummyView(deal)
    view._on_delay_to_event()

    assert Task.select().where(Task.is_done == True).count() == 0
    assert not view.tabs_inited

