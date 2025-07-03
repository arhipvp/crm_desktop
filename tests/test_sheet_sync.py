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
