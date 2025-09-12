import datetime

import pytest

from database.models import Client, Deal, Task
from services.task_crud import get_tasks_page, build_task_query


@pytest.mark.usefixtures("in_memory_db")
def test_get_tasks_page_invalid_sort_field_defaults_to_due_date():
    client = Client.create(name="C")
    deal = Deal.create(client=client, description="D", start_date=datetime.date.today())
    t1 = Task.create(title="T1", due_date=datetime.date(2023, 1, 1), deal=deal)
    t2 = Task.create(title="T2", due_date=datetime.date(2023, 1, 2), deal=deal)

    res = list(get_tasks_page(page=1, per_page=10, sort_field="bad", sort_order="desc"))
    assert [t.id for t in res] == [t2.id, t1.id]


@pytest.mark.usefixtures("in_memory_db")
def test_build_task_query_invalid_sort_field_no_executor_join():
    query = build_task_query(sort_field="bad")
    sql, _ = query.sql()
    assert "executor" not in sql.lower()
