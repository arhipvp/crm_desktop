from datetime import date

from database.models import Client, Policy
from services.policies.policy_app_service import PolicyAppService


def test_policy_app_service_distinct_values_include_null(in_memory_db):
    client = Client.create(name="Policy client")
    Policy.create(
        client=client,
        policy_number="POL-NULL",
        start_date=date.today(),
        sales_channel=None,
    )
    Policy.create(
        client=client,
        policy_number="POL-DIRECT",
        start_date=date.today(),
        sales_channel="Direct",
    )

    service = PolicyAppService()
    values = service.get_distinct_values("sales_channel")

    assert values, "Ожидались значения фильтра"
    assert values[0]["value"] is None
    assert values[0]["display"] == "—"
    assert any(item["value"] == "Direct" for item in values)

    filtered = service.get_distinct_values(
        "sales_channel",
        filters={"column_filters": {"sales_channel": ["Direct"]}},
    )
    assert all(item["value"] is not None for item in filtered)
