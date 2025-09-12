import datetime

import pytest

from database.models import Client, Deal, Task
from services.task_crud import get_tasks_page, build_task_query


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
