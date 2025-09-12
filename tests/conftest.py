import datetime
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QDate
from database.models import Client, Deal, Policy, Task, Executor, DealExecutor
from services.task_states import QUEUED
from ui.views.deal_detail.actions import DealActionsMixin
from ui.views.deal_detail.tabs import DealTabsMixin


TODAY = datetime.date(2024, 1, 1)


@pytest.fixture
def make_deal_with_executor():
    def _make_deal_with_executor(
        client_name: str = "C",
        deal_description: str = "D",
        executor_name: str = "E",
        tg_id: int = 1,
        *,
        is_active: bool = True,
    ):
        client = Client.create(name=client_name)
        deal = Deal.create(
            client=client,
            description=deal_description,
            start_date=TODAY,
        )
        executor = Executor.create(full_name=executor_name, tg_id=tg_id, is_active=is_active)
        DealExecutor.create(
            deal=deal,
            executor=executor,
            assigned_date=TODAY,
        )
        return client, deal, executor

    return _make_deal_with_executor


@pytest.fixture
def make_task():
    def _make_task(
        *,
        client: Client | None = None,
        deal: Deal | None = None,
        policy: Policy | None = None,
        client_name: str = "C",
        deal_description: str = "D",
        title: str = "T",
        due_date: datetime.date | None = None,
        dispatch_state: str = QUEUED,
        queued_at: datetime.datetime | None = None,
        **task_kwargs,
    ):
        if client is None:
            client = Client.create(name=client_name)
        if deal is None and policy is None:
            deal = Deal.create(
                client=client,
                description=deal_description,
                start_date=TODAY,
            )
        if due_date is None:
            due_date = TODAY
        params = {
            "title": title,
            "due_date": due_date,
            "dispatch_state": dispatch_state,
        }
        if deal is not None:
            params["deal"] = deal
        if policy is not None:
            params["policy"] = policy
        if queued_at is not None:
            params["queued_at"] = queued_at
        params.update(task_kwargs)
        task = Task.create(**params)
        return client, deal, task

    return _make_task


@pytest.fixture
def dummy_delay_view(monkeypatch):
    def _make(confirm_result: bool = True):
        from ui.forms import deal_next_event_dialog

        dummy_dialog = SimpleNamespace(
            exec=lambda: True, get_reminder_date=lambda: TODAY
        )
        monkeypatch.setattr(
            deal_next_event_dialog, "DealNextEventDialog", lambda *a, **k: dummy_dialog
        )
        monkeypatch.setattr(
            "ui.views.deal_detail.actions.confirm", lambda *a, **k: confirm_result
        )

        client = Client.create(name="C")
        deal = Deal.create(client=client, description="D", start_date=TODAY)
        Task.create(title="T1", due_date=TODAY, deal=deal)
        Task.create(title="T2", due_date=TODAY, deal=deal)

        class DummyView(DealActionsMixin):
            def __init__(self, deal):
                self.instance = deal
                self.tabs_inited = False

            def _collect_upcoming_events(self):
                return [("Event", TODAY)]

            def _init_tabs(self):
                self.tabs_inited = True

            def accept(self):
                pass

        return DummyView(deal)

    return _make


@pytest.fixture
def dummy_deal():
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

    return DummyDeal()
