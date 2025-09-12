from datetime import date, datetime, timedelta

import pytest

from database.models import Policy, Task
from services.task_queue import (
    pop_all_by_deal,
    pop_next,
    pop_next_by_client,
    pop_next_by_deal,
)
from services.task_states import QUEUED, SENT


@pytest.mark.usefixtures("in_memory_db")
def test_pop_next_returns_tasks_in_order_and_none_when_empty(make_task):
    earlier = datetime.utcnow() - timedelta(minutes=5)
    later = datetime.utcnow() - timedelta(minutes=1)
    client, deal, t1 = make_task(title="T1", queued_at=earlier)
    _, _, t2 = make_task(client=client, deal=deal, title="T2", queued_at=later)

    res1 = pop_next(chat_id=10)
    assert res1.id == t1.id
    assert res1.dispatch_state == SENT
    assert res1.tg_chat_id == 10

    res2 = pop_next(chat_id=10)
    assert res2.id == t2.id
    assert res2.dispatch_state == SENT
    assert res2.tg_chat_id == 10
    assert res1.dispatch_state == SENT


    assert pop_next(chat_id=10) is None


@pytest.mark.usefixtures("in_memory_db")
def test_pop_next_by_client_filters_by_client_and_policy(make_task):
    c1, d1, t_deal = make_task(
        client_name="C1",
        deal_description="D1",
        title="T_deal",
        queued_at=datetime.utcnow() - timedelta(minutes=2),
    )
    c2, d2, _ = make_task(client_name="C2", deal_description="D2", title="T_other")
    p1 = Policy.create(client=c1, policy_number="P1", start_date=date.today())
    _, _, t_policy = make_task(
        client=c1,
        policy=p1,
        deal=None,
        title="T_policy",
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
def test_pop_next_by_deal_filters_tasks(make_task):
    client, deal1, t1 = make_task(
        client_name="C",
        deal_description="D1",
        title="T1",
        queued_at=datetime.utcnow() - timedelta(minutes=1),
    )
    _, deal2, _ = make_task(
        client=client,
        deal_description="D2",
        title="T_other",
    )
    _, _, t2 = make_task(client=client, deal=deal1, title="T2", queued_at=datetime.utcnow())

    res1 = pop_next_by_deal(chat_id=30, deal_id=deal1.id)
    assert res1.id == t1.id
    assert res1.tg_chat_id == 30
    res2 = pop_next_by_deal(chat_id=30, deal_id=deal1.id)
    assert res2.id == t2.id
    assert res2.tg_chat_id == 30
    assert pop_next_by_deal(chat_id=30, deal_id=deal1.id) is None

    assert Task.get(Task.deal == deal2).dispatch_state == QUEUED


@pytest.mark.usefixtures("in_memory_db")
def test_pop_all_by_deal_returns_all_and_marks_sent(make_task):
    client, deal, t1 = make_task(
        title="T1", queued_at=datetime.utcnow() - timedelta(minutes=1)
    )
    _, _, t2 = make_task(client=client, deal=deal, title="T2", queued_at=datetime.utcnow())

    tasks = pop_all_by_deal(chat_id=40, deal_id=deal.id)
    assert [t.id for t in tasks] == [t1.id, t2.id]
    assert all(t.dispatch_state == SENT and t.tg_chat_id == 40 for t in tasks)
    assert pop_next_by_deal(chat_id=40, deal_id=deal.id) is None
