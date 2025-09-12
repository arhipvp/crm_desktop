import datetime
from datetime import date

import pytest

from database.models import Client, Deal, Policy, Task
from services.task_crud import build_task_query, get_tasks_page


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
def test_task_search_related_models(in_memory_db, search, expected):
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

    query = build_task_query(search_text=search)
    results = list(query)
    assert [r.title for r in results] == [expected]


@pytest.mark.usefixtures("in_memory_db")
@pytest.mark.parametrize(
    "func, requires_order",
    [
        (get_tasks_page, True),
        (build_task_query, False),
    ],
)
@pytest.mark.parametrize("sort_order", ["asc", "desc"])
def test_invalid_sort_field_defaults_to_due_date(func, requires_order, sort_order):
    client = Client.create(name="C")
    deal = Deal.create(client=client, description="D", start_date=datetime.date.today())
    t1 = Task.create(title="T1", due_date=datetime.date(2023, 1, 1), deal=deal)
    t2 = Task.create(title="T2", due_date=datetime.date(2023, 1, 2), deal=deal)

    kwargs = {"sort_field": "bad", "sort_order": sort_order}
    if func is get_tasks_page:
        kwargs.update(page=1, per_page=10)

    query = func(**kwargs)
    result = list(query)

    if requires_order:
        expected = [t1.id, t2.id] if sort_order == "asc" else [t2.id, t1.id]
        assert [t.id for t in result] == expected
    else:
        default_ids = {t.id for t in build_task_query()}
        assert {t.id for t in result} == default_ids
        sql, _ = query.sql()
        assert "executor" not in sql.lower()
