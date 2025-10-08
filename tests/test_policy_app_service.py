from datetime import date, timedelta
from types import SimpleNamespace

from database.models import Client, Policy
from services.policies.policy_app_service import PolicyAppService
from services.policies.dto import PolicyRowDTO
from services.policies.policy_table_controller import PolicyTableController


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


def test_policy_app_service_get_page_with_total_counts_before_pagination():
    client = Client.create(name="Paged client")
    for index in range(3):
        Policy.create(
            client=client,
            policy_number=f"POL-PAGE-{index}",
            start_date=date.today() + timedelta(days=index),
        )

    service = PolicyAppService()
    items, total = service.get_page_with_total(1, 2, order_by="policy_number")

    assert total == 3
    assert len(items) == 2
    assert all(isinstance(item, PolicyRowDTO) for item in items)


def test_policy_table_controller_reuses_total_from_page_request():
    class StubService:
        def __init__(self):
            self.count_calls = 0

        def get_page_with_total(self, page, per_page, **filters):
            return (
                [
                    PolicyRowDTO(
                        id=1,
                        client_id=None,
                        client_name="",
                        deal_id=None,
                        deal_description=None,
                        policy_number="POL-1",
                    )
                ],
                5,
            )

        def count(self, **filters):
            self.count_calls += 1
            return 5

    controller = PolicyTableController(SimpleNamespace(), service=StubService())

    items = controller._get_page(1, 10)
    assert len(items) == 1

    total = controller._get_total()
    assert total == 5
    assert controller._pending_total is None
    assert controller.service.count_calls == 0

    controller._get_total()
    assert controller._pending_total is None
    assert controller.service.count_calls == 1
