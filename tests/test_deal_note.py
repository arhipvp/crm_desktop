import pytest
from datetime import date
from services.client_service import add_client
from services.deal_service import add_deal
from database.models import Deal


def test_deal_note_on_create(test_db):
    client = add_client(name="Test")
    note = "Первый расчёт"
    deal = add_deal(
        client_id=client.id,
        start_date=date(2025, 1, 1),
        description="D",
        calculations=note,
    )
    deal = Deal.get_by_id(deal.id)
    assert deal.calculations, "Запись не сохранена"
    assert note in deal.calculations
    assert deal.calculations.startswith("[")
