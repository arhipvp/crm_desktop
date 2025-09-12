from datetime import date

from database.models import Client, Deal, DealCalculation
from services.calculation_service import (
    format_calculation,
    get_unique_calculation_field_values,
    update_calculation,
)


def test_update_calculation(in_memory_db):
    client = Client.create(name="C")
    deal1 = Deal.create(client=client, description="d1", start_date=date.today())
    deal2 = Deal.create(client=client, description="d2", start_date=date.today())
    calc = DealCalculation.create(deal=deal1, insurance_company="A")

    updated = update_calculation(
        calc, insurance_company="B", deal_id=deal2.id
    )

    assert updated.insurance_company == "B"
    assert updated.deal_id == deal2.id


def test_get_unique_calculation_field_values(in_memory_db):
    client = Client.create(name="C")
    deal = Deal.create(client=client, description="d", start_date=date.today())
    DealCalculation.create(deal=deal, insurance_company="A")
    DealCalculation.create(deal=deal, insurance_company="B")
    DealCalculation.create(deal=deal, insurance_company="A")
    DealCalculation.create(deal=deal, insurance_company=None)

    values = get_unique_calculation_field_values("insurance_company")

    assert values == ["A", "B"]


def test_format_calculation(in_memory_db):
    client = Client.create(name="C")
    deal = Deal.create(client=client, description="d", start_date=date.today())
    calc = DealCalculation.create(
        deal=deal,
        insurance_company="IC",
        insurance_type="Type",
        insured_amount=1000,
        premium=100,
        deductible=10,
        note="note",
    )

    formatted = format_calculation(calc)

    assert (
        formatted
        == "IC, Type: сумма 1 000 руб, премия 100 руб, франшиза 10 руб — note"
    )

