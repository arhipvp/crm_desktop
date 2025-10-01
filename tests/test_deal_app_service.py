from datetime import date

from database.models import Client, Deal
from services.deals.deal_app_service import DealAppService


def test_deal_app_service_count_accepts_ordering(in_memory_db):
    client = Client.create(name="Test Client")
    Deal.create(client=client, description="Test", start_date=date.today())

    service = DealAppService()

    assert service.count(order_by="client_name", order_dir="desc") == 1
