from datetime import date

import pytest

from database.models import Client, Deal
from services.deals.deal_table_controller import DealTableController
from services.deals.dto import deal_to_row_dto
from ui.views.deal_table_view import DealTableView


@pytest.mark.usefixtures("ui_settings_temp_path")
def test_edit_selected_default_loads_instance(
    monkeypatch, qapp, in_memory_db
):
    client = Client.create(name="Test Client")
    deal = Deal.create(client=client, description="Test", start_date=date.today())
    dto = deal_to_row_dto(deal)

    monkeypatch.setattr(DealTableController, "get_statuses", lambda self: [])

    def fake_load_data(self):
        self._apply_items([dto], total_count=1)

    monkeypatch.setattr(DealTableController, "load_data", fake_load_data)

    load_call = {"id": None}

    def fake_load_deal(self, deal_id: int):
        load_call["id"] = deal_id
        return deal

    monkeypatch.setattr(DealTableController, "load_deal", fake_load_deal)

    refreshed = {"called": False}

    def fake_refresh(self):
        refreshed["called"] = True

    monkeypatch.setattr(DealTableController, "refresh", fake_refresh)

    captured: dict[str, object] = {}

    class DummyDetailView:
        def __init__(self, instance, parent=None, **kwargs):
            captured["instance"] = instance

        def exec(self):
            captured["exec"] = True
            return 0

    monkeypatch.setattr(
        "ui.views.deal_table_view.DealDetailView", DummyDetailView, raising=False
    )

    view = DealTableView()
    qapp.processEvents()
    view.table.selectRow(0)

    view._on_edit()

    assert captured.get("exec") is True
    assert captured.get("instance") is deal
    assert load_call["id"] == deal.id
    assert refreshed["called"] is True

    view.deleteLater()
