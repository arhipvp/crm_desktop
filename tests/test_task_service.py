import datetime
from datetime import date

import pytest

from database.models import Client, Deal, Policy, Task
from database.db import db
from services.task_crud import (
    build_task_query,
    fetch_tasks_page_with_total,
    get_tasks_page,
)


@pytest.mark.parametrize("use_fetch", [False, True])
@pytest.mark.parametrize(
    "search, expected",
    [
        ("T1", "T1"),
        ("N1", "T1"),
        ("DealA", "T1"),
        ("P1", "T1"),
        ("Alice", "T1"),
    ],
)
def test_task_search_related_models(in_memory_db, search, expected, use_fetch):
    client1 = Client.create(name="Alice")
    deal1 = Deal.create(
        client=client1, description="DealA", start_date=date.today()
    )
    policy1 = Policy.create(
        client=client1, deal=deal1, policy_number="P1", start_date=date.today()
    )
    Task.create(
        title="T1",
        note="N1",
        deal=deal1,
        policy=policy1,
        due_date=date.today(),
    )

    client2 = Client.create(name="Bob")
    deal2 = Deal.create(
        client=client2, description="DealB", start_date=date.today()
    )
    policy2 = Policy.create(
        client=client2, deal=deal2, policy_number="P2", start_date=date.today()
    )
    Task.create(
        title="T2",
        note="N2",
        deal=deal2,
        policy=policy2,
        due_date=date.today(),
    )

    if use_fetch:
        query, total = fetch_tasks_page_with_total(
            page=1, per_page=10, search_text=search
        )
        results = list(query)
        assert total == 1
    else:
        query = build_task_query(search_text=search)
        results = list(query)
    assert [r.title for r in results] == [expected]


@pytest.mark.usefixtures("in_memory_db")
@pytest.mark.parametrize(
    "func, requires_order",
    [
        (get_tasks_page, True),
        (build_task_query, False),
        (fetch_tasks_page_with_total, True),
    ],
)
@pytest.mark.parametrize("sort_order", ["asc", "desc"])
def test_invalid_sort_field_defaults_to_due_date(func, requires_order, sort_order):
    client = Client.create(name="C")
    deal = Deal.create(client=client, description="D", start_date=datetime.date.today())
    t1 = Task.create(title="T1", due_date=datetime.date(2023, 1, 1), deal=deal)
    t2 = Task.create(title="T2", due_date=datetime.date(2023, 1, 2), deal=deal)

    kwargs = {"sort_field": "bad", "sort_order": sort_order}
    if func is get_tasks_page or func is fetch_tasks_page_with_total:
        kwargs.update(page=1, per_page=10)

    result = func(**kwargs)
    if func is fetch_tasks_page_with_total:
        query, total = result
        assert total == 2
    else:
        query = result
    result_list = list(query)

    if requires_order:
        expected = [t1.id, t2.id] if sort_order == "asc" else [t2.id, t1.id]
        assert [t.id for t in result_list] == expected
    else:
        default_ids = {t.id for t in build_task_query()}
        assert {t.id for t in result_list} == default_ids
        sql, _ = query.sql()
        assert "executor" not in sql.lower()


@pytest.mark.usefixtures("in_memory_db")
def test_fetch_tasks_page_with_total_executes_two_queries(monkeypatch):
    client = Client.create(name="C")
    deal = Deal.create(client=client, description="D", start_date=date.today())
    Task.create(title="Active", due_date=date.today(), deal=deal)
    Task.create(title="Done", due_date=date.today(), deal=deal, is_done=True)

    database = db.obj
    executed: list[str] = []
    original_execute_sql = database.execute_sql

    def spy(sql, params=None, *args, **kwargs):
        executed.append(sql)
        return original_execute_sql(sql, params, *args, **kwargs)

    monkeypatch.setattr(database, "execute_sql", spy)

    query, total = fetch_tasks_page_with_total(
        page=1,
        per_page=10,
        include_done=False,
    )
    results = list(query)

    assert len(results) == 1
    assert total == 1
    assert len(executed) <= 2


@pytest.mark.usefixtures("in_memory_db")
def test_fetch_tasks_page_with_total_respects_filters():
    client = Client.create(name="Alice")
    deal = Deal.create(client=client, description="Important", start_date=date.today())
    other_deal = Deal.create(
        client=client, description="Secondary", start_date=date.today()
    )
    policy = Policy.create(
        client=client,
        deal=deal,
        policy_number="POL-1",
        start_date=date.today(),
    )
    Task.create(
        title="Main",
        note="primary",
        deal=deal,
        due_date=date.today(),
        dispatch_state="queued",
    )
    Task.create(
        title="Secondary",
        deal=other_deal,
        due_date=date.today(),
        is_done=True,
    )
    Task.create(
        title="Policy",
        policy=policy,
        due_date=date.today(),
    )

    query, total = fetch_tasks_page_with_total(
        page=1,
        per_page=10,
        include_done=False,
        search_text="main",
        deal_id=deal.id,
    )

    titles = [task.title for task in query]

    assert titles == ["Main"]
    assert total == 1
