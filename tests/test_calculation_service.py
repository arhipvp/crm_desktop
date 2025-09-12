from datetime import date

import pytest

from database.models import Client, Deal, DealCalculation
from services.calculation_service import (
    format_calculation,
    get_unique_calculation_field_values,
    mark_calculations_deleted,
    update_calculation,
)


@pytest.fixture
def make_calculation():
    def _make_calculation(*, client=None, deal=None, **calc_kwargs):
        if client is None:
            client = Client.create(name="C")
        if deal is None:
            deal = Deal.create(client=client, description="d", start_date=date.today())
        calc = DealCalculation.create(deal=deal, **calc_kwargs)
        return client, deal, calc

    return _make_calculation


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


class TestMarkCalculationsDeleted:
    def test_marks_calculations_deleted(self, in_memory_db, make_calculation):
        _, deal, calc1 = make_calculation()
        _, _, calc2 = make_calculation(deal=deal)

        affected = mark_calculations_deleted([calc1.id, calc2.id])

        assert affected == 2
        assert DealCalculation.get_by_id(calc1.id).is_deleted
        assert DealCalculation.get_by_id(calc2.id).is_deleted

    def test_empty_ids(self, in_memory_db):
        affected = mark_calculations_deleted([])

        assert affected == 0
        assert DealCalculation.select().count() == 0

    def test_missing_ids(self, in_memory_db):
        affected = mark_calculations_deleted([1, 2, 3])

        assert affected == 0

