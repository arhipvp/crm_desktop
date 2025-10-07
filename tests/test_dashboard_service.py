from datetime import date, datetime

from database.models import Client, Deal, Policy, Task
from services.dashboard_service import get_dashboard_counters
from services.task_states import SENT


def test_dashboard_counters_with_data(db_transaction):
    today = date.today()

    active_client = Client.create(name="Active client")
    active_deal = Deal.create(
        client=active_client,
        description="Active deal",
        start_date=today,
    )
    Policy.create(
        client=active_client,
        deal=active_deal,
        policy_number="POL-1",
        start_date=today,
    )

    Task.create(
        title="Queued task",
        due_date=today,
        deal=active_deal,
        queued_at=datetime.now(),
    )
    Task.create(
        title="Working task",
        due_date=today,
        deal=active_deal,
        tg_chat_id=123,
    )
    Task.create(
        title="Unconfirmed task",
        due_date=today,
        deal=active_deal,
        note="Needs confirmation",
    )
    Task.create(
        title="Assistant task",
        due_date=today,
        deal=active_deal,
        dispatch_state=SENT,
    )

    Client.create(name="Deleted client", is_deleted=True)
    Deal.create(
        client=active_client,
        description="Deleted deal",
        start_date=today,
        is_deleted=True,
    )
    Policy.create(
        client=active_client,
        deal=active_deal,
        policy_number="POL-DEL",
        start_date=today,
        is_deleted=True,
    )
    Task.create(
        title="Deleted task",
        due_date=today,
        deal=active_deal,
        queued_at=datetime.now(),
        is_deleted=True,
        note="Should not count",
    )

    counters = get_dashboard_counters()

    assert counters["entities"] == {
        "clients": 1,
        "deals": 1,
        "policies": 1,
        "tasks": 4,
    }
    assert counters["tasks"] == {
        "assistant": 1,
        "sent": 1,
        "working": 1,
        "unconfirmed": 1,
    }


def test_dashboard_counters_empty(db_transaction):
    counters = get_dashboard_counters()

    assert counters["entities"] == {
        "clients": 0,
        "deals": 0,
        "policies": 0,
        "tasks": 0,
    }
    assert counters["tasks"] == {
        "assistant": 0,
        "sent": 0,
        "working": 0,
        "unconfirmed": 0,
    }
