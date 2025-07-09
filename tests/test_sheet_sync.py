from datetime import date

import pytest

from services.task_service import add_task, get_all_tasks
from services import sheets_service


def test_sync_creates_tasks(monkeypatch):
    data = [
        ["title", "due_date", "note"],
        ["A", "2025-01-01", ""],
        ["B", "2025-01-02", "hi"],
    ]
    monkeypatch.setattr(sheets_service, "read_sheet", lambda sid, rn: data)
    monkeypatch.setenv("GOOGLE_SHEETS_TASKS_ID", "x")
    monkeypatch.setattr(sheets_service, "GOOGLE_SHEETS_TASKS_ID", "x", raising=False)

    added = sheets_service.sync_tasks_from_sheet()

    titles = [t.title for t in get_all_tasks()]
    assert set(titles) == {"A", "B"}
    assert added == 2


def test_sync_updates_existing(monkeypatch):
    add_task(title="C", due_date=date(2025, 1, 3), note="old")
    data = [
        ["title", "due_date", "note"],
        ["C", "2025-01-03", "new"],
    ]
    monkeypatch.setattr(sheets_service, "read_sheet", lambda sid, rn: data)
    monkeypatch.setenv("GOOGLE_SHEETS_TASKS_ID", "x")
    monkeypatch.setattr(sheets_service, "GOOGLE_SHEETS_TASKS_ID", "x", raising=False)

    sheets_service.sync_tasks_from_sheet()

    updated = get_all_tasks()[0]
    assert updated.note == "new"


def test_sync_calculations(monkeypatch):
    from services.calculation_service import get_calculations
    from services.client_service import add_client
    from services.deal_service import add_deal

    client = add_client(name="C")
    deal = add_deal(client_id=client.id, start_date=date(2025, 1, 1), description="D")

    data = [
        [
            "deal_id",
            "insurance_company",
            "insurance_type",
            "insured_amount",
            "premium",
            "deductible",
            "note",
        ],
        [str(deal.id), "СК", "КАСКО", "1000", "10", "0", ""],
    ]

    monkeypatch.setattr(sheets_service, "read_sheet", lambda sid, rn: data)
    monkeypatch.setenv("GOOGLE_SHEETS_CALCULATIONS_ID", "x")
    monkeypatch.setattr(sheets_service, "GOOGLE_SHEETS_CALCULATIONS_ID", "x", raising=False)

    added = sheets_service.sync_calculations_from_sheet()

    calcs = list(get_calculations(deal.id))
    assert added == 1
    assert len(calcs) == 1

    # повторный запуск не должен создавать дубликаты
    added_again = sheets_service.sync_calculations_from_sheet()
    calcs_again = list(get_calculations(deal.id))
    assert added_again == 0
    assert len(calcs_again) == 1


def test_sync_calculations_normalization(monkeypatch):
    from services.calculation_service import get_calculations
    from services.client_service import add_client
    from services.deal_service import add_deal

    client = add_client(name="C")
    deal = add_deal(client_id=client.id, start_date=date(2025, 1, 1), description="D")

    data = [
        [
            "deal_id",
            "insurance_company",
            "insurance_type",
            "insured_amount",
            "premium",
            "deductible",
            "note",
        ],
        [str(deal.id), "сбер", "КАСКО", "646\xa0355", "26646", "", "смирнов, не офд"],
    ]

    monkeypatch.setattr(sheets_service, "read_sheet", lambda sid, rn: data)
    monkeypatch.setenv("GOOGLE_SHEETS_CALCULATIONS_ID", "x")
    monkeypatch.setattr(sheets_service, "GOOGLE_SHEETS_CALCULATIONS_ID", "x", raising=False)

    sheets_service.sync_calculations_from_sheet()

    calc = list(get_calculations(deal.id))[0]
    assert calc.insurance_company == "Сбер"
    assert calc.insured_amount == 646355
    assert calc.premium == 26646
    assert calc.note == "смирнов, не офд"

