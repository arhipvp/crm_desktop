from datetime import date, timedelta

import pytest

from database.models import Task
from ui.views.deal_detail import tabs


@pytest.mark.usefixtures("in_memory_db")
@pytest.mark.parametrize(
    "confirm_result, closed_count",
    [
        (True, 2),
        (False, 0),
    ],
)
def test_tasks_closed_depends_on_confirm(
    dummy_delay_view, confirm_result, closed_count
):
    view = dummy_delay_view(confirm_result)
    view._on_delay_to_event()

    assert Task.select().where(Task.is_done == True).count() == closed_count
    assert view.tabs_inited == confirm_result


def test_postpone_reminder_uses_today(monkeypatch, dummy_deal):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2024, 4, 8)

    monkeypatch.setattr(tabs, "date", FixedDate)

    dummy_deal._postpone_reminder(2)

    assert dummy_deal.reminder_date._date.toPython() == FixedDate.today() + timedelta(
        days=2
    )
    assert dummy_deal.saved

