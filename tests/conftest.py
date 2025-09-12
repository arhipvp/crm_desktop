import datetime
import pytest
from database.models import Client, Deal, Policy, Task, Executor, DealExecutor
from services.task_states import QUEUED


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
