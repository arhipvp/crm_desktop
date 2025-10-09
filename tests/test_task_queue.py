from datetime import date, datetime, timedelta

import pytest

from database.models import Task
from services.task_queue import (
    get_all_deals_with_queued_tasks,
    get_deals_with_queued_tasks,
    get_clients_with_queued_tasks,
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
def test_pop_next_by_client_filters_by_client_and_policy(
    make_task, make_policy_with_payment
):
    c1, d1, t_deal = make_task(
        client_name="C1",
        deal_description="D1",
        title="T_deal",
        queued_at=datetime.utcnow() - timedelta(minutes=2),
    )
    c2, d2, _ = make_task(client_name="C2", deal_description="D2", title="T_other")
    _, _, p1, _ = make_policy_with_payment(
        client=c1, policy_kwargs={"policy_number": "P1"}
    )
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


@pytest.mark.usefixtures("in_memory_db")
def test_get_deals_with_queued_tasks_excludes_deleted_deals(make_task):
    client, active_deal, _ = make_task(title="Active deal task")
    _, deleted_deal, _ = make_task(
        client=client,
        deal_description="Deleted",
        title="Deleted deal task",
    )
    deleted_deal.is_deleted = True
    deleted_deal.save()

    deals = get_deals_with_queued_tasks(client.id)

    assert {deal.id for deal in deals} == {active_deal.id}


@pytest.mark.usefixtures("in_memory_db")
def test_get_all_deals_with_queued_tasks_excludes_deleted_deals(make_task):
    client, active_deal, _ = make_task(title="Active task")
    _, deleted_deal, _ = make_task(
        client=client,
        deal_description="Deleted",
        title="Deleted task",
    )
    deleted_deal.is_deleted = True
    deleted_deal.save()

    deals = get_all_deals_with_queued_tasks()

    assert {deal.id for deal in deals} == {active_deal.id}


@pytest.mark.usefixtures("in_memory_db")
def test_get_clients_with_queued_tasks_excludes_deleted_entities(
    make_task, make_policy_with_payment
):
    deleted_client, _, _ = make_task(client_name="Deleted client")
    deleted_client.is_deleted = True
    deleted_client.save()

    _, deleted_deal, _ = make_task(client_name="Client with deleted deal")
    deleted_deal.is_deleted = True
    deleted_deal.save()

    policy_client, _, deleted_policy, _ = make_policy_with_payment(
        client_kwargs={"name": "Client with deleted policy"},
        policy_kwargs={"policy_number": "DP"},
    )
    deleted_policy.is_deleted = True
    deleted_policy.save()
    make_task(client=policy_client, deal=None, policy=deleted_policy, title="Policy task")

    active_client, _, _ = make_task(client_name="Active client", title="Active task")

    clients = get_clients_with_queued_tasks()

    assert {client.id for client in clients} == {active_client.id}
