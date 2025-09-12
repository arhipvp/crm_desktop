from datetime import date

from database.models import Client, Deal, DealCalculation
from services.calculation_service import mark_calculations_deleted


def test_mark_calculations_deleted(in_memory_db):
    DealCalculation.create_table()
    try:
        client = Client.create(name="C")
        deal = Deal.create(client=client, description="d", start_date=date.today())
        calc1 = DealCalculation.create(deal=deal)
        calc2 = DealCalculation.create(deal=deal)

        affected = mark_calculations_deleted([calc1.id, calc2.id])

        assert affected == 2
        assert DealCalculation.get_by_id(calc1.id).is_deleted
        assert DealCalculation.get_by_id(calc2.id).is_deleted
    finally:
        DealCalculation.drop_table()


def test_mark_calculations_deleted_empty_ids(in_memory_db):
    DealCalculation.create_table()
    try:
        affected = mark_calculations_deleted([])

        assert affected == 0
        assert DealCalculation.select().count() == 0
    finally:
        DealCalculation.drop_table()


def test_mark_calculations_deleted_missing(in_memory_db):
    DealCalculation.create_table()
    try:
        affected = mark_calculations_deleted([1, 2, 3])

        assert affected == 0
    finally:
        DealCalculation.drop_table()
