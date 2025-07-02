from datetime import date

from services.client_service import add_client
from services.deal_service import add_deal
from services.calculation_service import add_calculation
from database.models import Deal


def test_calculation_not_added_to_journal():
    client = add_client(name="Клиент")
    deal = add_deal(client_id=client.id, start_date=date(2025, 1, 1), description="Тест")
    assert deal.calculations is None

    add_calculation(deal.id, insurance_company="СК", premium=1000)
    deal = Deal.get_by_id(deal.id)
    assert not deal.calculations
