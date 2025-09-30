import datetime
import os
from datetime import date
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication
from database.models import Client, Deal, Policy, Task, Executor, DealExecutor, Payment
from services.task_states import QUEUED
from ui.views.deal_detail.actions import DealActionsMixin
from ui.views.deal_detail.tabs import DealTabsMixin


@pytest.fixture(scope="session")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def stub_drive_gateway(tmp_path):
    return SimpleNamespace(local_root=tmp_path)


@pytest.fixture
def stub_app_context(stub_drive_gateway):
    return SimpleNamespace(drive_gateway=stub_drive_gateway)


@pytest.fixture
def stub_client_app_service(monkeypatch):
    from services.clients.dto import ClientDetailsDTO

    class StubClientAppService:
        def __init__(self):
            self.similar: list = []
            self.created_commands: list = []
            self.updated_commands: list = []
            self.deleted_ids: list = []
            self.next_created: ClientDetailsDTO | None = None
            self.next_updated: ClientDetailsDTO | None = None

        def find_similar(self, _name: str):
            return self.similar

        def create(self, command):
            self.created_commands.append(command)
            if self.next_created is None:
                raise AssertionError("next_created не установлен для create")
            return self.next_created

        def update(self, command):
            self.updated_commands.append(command)
            if self.next_updated is None:
                raise AssertionError("next_updated не установлен для update")
            return self.next_updated

        def delete_many(self, client_ids):
            self.deleted_ids.extend(client_ids)

        # заглушки на случай вызовов, которые не нужны в конкретном тесте
        def get_page(self, *args, **kwargs):
            return []

        def count(self, *args, **kwargs):
            return 0

        def get_detail(self, client_id: int):
            if self.next_updated and self.next_updated.id == client_id:
                return self.next_updated
            if self.next_created and self.next_created.id == client_id:
                return self.next_created
            raise LookupError(f"Нет данных для клиента {client_id}")

        def get_merge_candidates(self, *_args, **_kwargs):  # pragma: no cover - не используется
            return []

        def merge(self, *_args, **_kwargs):  # pragma: no cover - не используется
            return None

    stub = StubClientAppService()
    targets = [
        "services.clients.client_app_service.client_app_service",
        "services.clients.client_table_controller.client_app_service",
        "ui.forms.client_form.client_app_service",
        "ui.views.client_table_view.client_app_service",
        "ui.views.client_detail_view.client_app_service",
    ]
    for target in targets:
        monkeypatch.setattr(target, stub, raising=False)
    return stub


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
            start_date=datetime.date.today(),
        )
        executor = Executor.create(full_name=executor_name, tg_id=tg_id, is_active=is_active)
        DealExecutor.create(
            deal=deal,
            executor=executor,
            assigned_date=datetime.date.today(),
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
                start_date=datetime.date.today(),
            )
        if due_date is None:
            due_date = datetime.date.today()
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
def make_policy_with_payment():
    def _make_policy_with_payment(
        *,
        client: Client | None = None,
        deal: Deal | None = None,
        client_kwargs: dict | None = None,
        deal_kwargs: dict | None = None,
        policy_kwargs: dict | None = None,
        payment_kwargs: dict | None = None,
    ):
        if client is None:
            client_kwargs = client_kwargs or {"name": "C"}
            client = Client.create(**client_kwargs)
        if deal is None:
            deal_defaults = {"description": "D", "start_date": date.today()}
            deal_params = {**deal_defaults, **(deal_kwargs or {})}
            deal = Deal.create(client=client, **deal_params)
        policy_defaults = {"policy_number": "P", "start_date": date.today()}
        policy_params = {**policy_defaults, **(policy_kwargs or {})}
        policy_params.setdefault("client", client)
        policy_params.setdefault("deal", deal)
        policy = Policy.create(**policy_params)
        payment_defaults = {"amount": 100, "payment_date": date.today()}
        payment_params = {**payment_defaults, **(payment_kwargs or {})}
        payment_params.setdefault("policy", policy)
        payment = Payment.create(**payment_params)
        return client, deal, policy, payment

    return _make_policy_with_payment


@pytest.fixture
def dummy_delay_view(monkeypatch):
    def _make(confirm_result: bool = True):
        from ui.forms import deal_next_event_dialog

        dummy_dialog = SimpleNamespace(
            exec=lambda: True, get_reminder_date=lambda: date.today()
        )
        monkeypatch.setattr(
            deal_next_event_dialog, "DealNextEventDialog", lambda *a, **k: dummy_dialog
        )
        monkeypatch.setattr(
            "ui.views.deal_detail.actions.confirm", lambda *a, **k: confirm_result
        )

        client = Client.create(name="C")
        deal = Deal.create(client=client, description="D", start_date=date.today())
        Task.create(title="T1", due_date=date.today(), deal=deal)
        Task.create(title="T2", due_date=date.today(), deal=deal)

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
