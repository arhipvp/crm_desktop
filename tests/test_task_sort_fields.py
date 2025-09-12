from datetime import date

import pytest

from database.models import Client, Deal, Task
from services.task_crud import build_task_query, get_tasks_page


@pytest.mark.usefixtures("in_memory_db")
def test_get_tasks_page_invalid_sort_field_defaults_to_due_date():
    client = Client.create(name="C")
    deal = Deal.create(client=client, description="D", start_date=date.today())
    t1 = Task.create(title="T1", due_date=date(2024, 1, 1), deal=deal)
    t2 = Task.create(title="T2", due_date=date(2024, 1, 2), deal=deal)

    tasks = list(get_tasks_page(page=1, per_page=10, sort_field="unknown", sort_order="asc"))
    assert [t.id for t in tasks] == [t1.id, t2.id]


@pytest.mark.usefixtures("in_memory_db")
def test_build_task_query_invalid_sort_field_behaves_as_default():
    client = Client.create(name="C")
    deal = Deal.create(client=client, description="D", start_date=date.today())
    Task.create(title="T1", due_date=date.today(), deal=deal)
    Task.create(title="T2", due_date=date.today(), deal=deal)

    ids_default = {t.id for t in build_task_query()}
    ids_invalid = {t.id for t in build_task_query(sort_field="bad_field")}
    assert ids_invalid == ids_default
