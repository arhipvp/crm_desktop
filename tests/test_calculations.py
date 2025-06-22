from datetime import date
from services.client_service import add_client
from services.deal_service import add_deal
from services.calculation_service import (
    add_calculation,
    get_calculations,
    mark_calculation_deleted,
    generate_offer_text,
)
from database.models import DealCalculation


def test_add_and_delete_calculation():
    client = add_client(name="Calc")
    deal = add_deal(client_id=client.id, start_date=date(2025, 1, 1), description="D")

    calc = add_calculation(deal.id, note="entry", insured_amount=100, premium=10)
    calcs = list(get_calculations(deal.id))
    assert calc in calcs

    mark_calculation_deleted(calc.id)
    remaining = list(get_calculations(deal.id))
    assert calc not in remaining

    # Проверим формирование предложения
    txt = generate_offer_text(calcs)
    assert "премия" in txt

