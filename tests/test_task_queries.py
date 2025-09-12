import datetime
import pytest

from database.models import Client, Deal, Policy, Task
from services.task_crud import build_task_query


TODAY = datetime.date(2024, 1, 1)


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
        client=client1, description="DealA", start_date=TODAY
    )
    policy1 = Policy.create(
        client=client1, deal=deal1, policy_number="P1", start_date=TODAY
    )
    Task.create(
        title="T1",
        note="N1",
        deal=deal1,
        policy=policy1,
        due_date=TODAY,
    )

    client2 = Client.create(name="Bob")
    deal2 = Deal.create(
        client=client2, description="DealB", start_date=TODAY
    )
    policy2 = Policy.create(
        client=client2, deal=deal2, policy_number="P2", start_date=TODAY
    )
    Task.create(
        title="T2",
        note="N2",
        deal=deal2,
        policy=policy2,
        due_date=TODAY,
    )

    query = build_task_query(search_text=search)
    results = list(query)
    assert [r.title for r in results] == [expected]
