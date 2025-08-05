import pytest
from services.client_service import add_client
from services.deal_service import add_deal
from ui.views.deal_detail_view import DealDetailView
from ui import settings as ui_settings


def test_deal_detail_view_settings_persist(tmp_path, qtbot, monkeypatch, test_db):
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(ui_settings, "SETTINGS_PATH", settings_path)

    client = add_client(name="A")
    deal1 = add_deal(client_id=client.id, start_date="2025-01-01", description="D1")

    view1 = DealDetailView(deal1)
    qtbot.addWidget(view1)
    view1.show()
    view1.resize(800, 600)
    qtbot.wait(50)
    view1.main_splitter.setSizes([200, 400])
    view1.tabs.setCurrentIndex(1)
    qtbot.wait(50)
    view1.close()
    qtbot.wait(50)

    deal2 = add_deal(client_id=client.id, start_date="2025-02-01", description="D2")
    view2 = DealDetailView(deal2)
    qtbot.addWidget(view2)
    view2.show()
    qtbot.wait(50)

    assert view2.size().width() == 800
    assert view2.size().height() == 600
    assert view2.tabs.currentIndex() == 1
    assert view2.main_splitter.sizes() == [200, 400]

    view2.close()
