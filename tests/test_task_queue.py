from datetime import date, datetime, timedelta

import pytest

from database.models import Client, Deal, Policy, Task
from services.task_queue import (
    pop_all_by_deal,
    pop_next,
    pop_next_by_client,
    pop_next_by_deal,
)
from services.task_states import QUEUED, SENT


@pytest.mark.usefixtures("in_memory_db")
def test_pop_next_returns_tasks_in_order_and_none_when_empty():
    client = Client.create(name="C")
    deal = Deal.create(client=client, description="D", start_date=date.today())
    earlier = datetime.utcnow() - timedelta(minutes=5)
    later = datetime.utcnow() - timedelta(minutes=1)
    t1 = Task.create(
        title="T1",
        due_date=date.today(),
        deal=deal,
        dispatch_state=QUEUED,
        queued_at=earlier,
    )
    t2 = Task.create(
        title="T2",
        due_date=date.today(),
        deal=deal,
        dispatch_state=QUEUED,
        queued_at=later,
    )

    res1 = pop_next(chat_id=10)
    assert res1.id == t1.id
    assert res1.dispatch_state == "sent"
    assert res1.tg_chat_id == 10

    res2 = pop_next(chat_id=10)
    assert res2.id == t2.id
    assert res2.dispatch_state == "sent"
    assert res2.tg_chat_id == 10
    assert res1.dispatch_state == SENT


    assert pop_next(chat_id=10) is None


@pytest.mark.usefixtures("in_memory_db")
def test_pop_next_by_client_filters_by_client_and_policy():
    c1 = Client.create(name="C1")
    c2 = Client.create(name="C2")
    d1 = Deal.create(client=c1, description="D1", start_date=date.today())
    d2 = Deal.create(client=c2, description="D2", start_date=date.today())
    p1 = Policy.create(client=c1, policy_number="P1", start_date=date.today())

    Task.create(
        title="T_other",
        due_date=date.today(),
        deal=d2,
        dispatch_state=QUEUED,
        queued_at=datetime.utcnow(),
    )
    t_deal = Task.create(
        title="T_deal",
        due_date=date.today(),
        deal=d1,
        dispatch_state=QUEUED,
        queued_at=datetime.utcnow() - timedelta(minutes=2),
    )
    t_policy = Task.create(
        title="T_policy",
        due_date=date.today(),
        policy=p1,
        dispatch_state=QUEUED,
        queued_at=datetime.utcnow() - timedelta(minutes=1),
    )

    r1 = pop_next_by_client(chat_id=20, client_id=c1.id)
    assert r1.id == t_deal.id
    assert r1.tg_chat_id == 20
    r2 = pop_next_by_client(chat_id=20, client_id=c1.id)
    assert r2.id == t_policy.id
    assert r2.tg_chat_id == 20
    assert pop_next_by_client(chat_id=20, client_id=c1.id) is None

    other = Task.get(Task.deal == d2)
    assert other.dispatch_state == QUEUED


@pytest.mark.usefixtures("in_memory_db")
def test_pop_next_by_deal_filters_tasks():
    client = Client.create(name="C")
    deal1 = Deal.create(client=client, description="D1", start_date=date.today())
    deal2 = Deal.create(client=client, description="D2", start_date=date.today())
    Task.create(
        title="T_other",
        due_date=date.today(),
        deal=deal2,
        dispatch_state=QUEUED,
        queued_at=datetime.utcnow(),
    )
    t1 = Task.create(
        title="T1",
        due_date=date.today(),
        deal=deal1,
        dispatch_state=QUEUED,
        queued_at=datetime.utcnow() - timedelta(minutes=1),
    )
    t2 = Task.create(
        title="T2",
        due_date=date.today(),
        deal=deal1,
        dispatch_state=QUEUED,
        queued_at=datetime.utcnow(),
    )

    res1 = pop_next_by_deal(chat_id=30, deal_id=deal1.id)
    assert res1.id == t1.id
    assert res1.tg_chat_id == 30
    res2 = pop_next_by_deal(chat_id=30, deal_id=deal1.id)
    assert res2.id == t2.id
    assert res2.tg_chat_id == 30
    assert pop_next_by_deal(chat_id=30, deal_id=deal1.id) is None

    assert Task.get(Task.deal == deal2).dispatch_state == QUEUED


@pytest.mark.usefixtures("in_memory_db")
def test_pop_all_by_deal_returns_all_and_marks_sent():
    client = Client.create(name="C")
    deal = Deal.create(client=client, description="D", start_date=date.today())
    t1 = Task.create(
        title="T1",
        due_date=date.today(),
        deal=deal,
        dispatch_state=QUEUED,
        queued_at=datetime.utcnow() - timedelta(minutes=1),
    )
    t2 = Task.create(
        title="T2",
        due_date=date.today(),
        deal=deal,
        dispatch_state=QUEUED,
        queued_at=datetime.utcnow(),
    )

    tasks = pop_all_by_deal(chat_id=40, deal_id=deal.id)
    assert [t.id for t in tasks] == [t1.id, t2.id]
    assert all(t.dispatch_state == SENT and t.tg_chat_id == 40 for t in tasks)
    assert pop_next_by_deal(chat_id=40, deal_id=deal.id) is None
