from datetime import date

from database.models import Client, Deal
from services.deals.deal_app_service import DealAppService


def test_deal_app_service_count_accepts_ordering(in_memory_db):
    client = Client.create(name="Test Client")
    Deal.create(client=client, description="Test", start_date=date.today())

    service = DealAppService()

    assert service.count(order_by="client_name", order_dir="desc") == 1


def test_deal_app_service_column_filters_multiple_values(in_memory_db):
    client = Client.create(name="Client")
    deal_new = Deal.create(
        client=client,
        description="New deal",
        status="new",
        start_date=date.today(),
    )
    deal_closed = Deal.create(
        client=client,
        description="Closed deal",
        status="closed",
        start_date=date.today(),
    )
    Deal.create(
        client=client,
        description="Other deal",
        status="other",
        start_date=date.today(),
    )

    service = DealAppService()
    converted = service._convert_column_filters({"status": ["new", "closed"]})
    assert Deal.status in converted
    assert converted[Deal.status] == ["new", "closed"]

    query = service._build_query(column_filters=converted)
    sql, params = query.sql()
    assert " OR " in sql
    assert params.count("%new%") == 1
    assert params.count("%closed%") == 1

    results = list(query)
    assert {deal.id for deal in results} == {deal_new.id, deal_closed.id}
