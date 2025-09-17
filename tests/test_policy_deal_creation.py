from __future__ import annotations

import datetime as dt

from PySide6.QtWidgets import QDialog

from database.models import Client, Deal, Policy
from ui.views.policy_table_view import PolicyTableView


def test_make_deal_sets_automatic_status(monkeypatch, in_memory_db, qapp):
    monkeypatch.setattr(PolicyTableView, "load_data", lambda self: None)
    monkeypatch.setattr(
        "services.deal_service.create_deal_folder", lambda *a, **k: (None, None)
    )

    class DummyDealDetail:
        def __init__(self, deal, parent=None):
            self.deal = deal
            self.parent = parent

        def exec(self):
            return QDialog.Accepted

    monkeypatch.setattr("ui.views.deal_detail.DealDetailView", DummyDealDetail)

    updates: list[tuple[int, int | None]] = []

    def fake_update_policy(policy_obj, deal_id=None, **kwargs):
        policy_obj.deal_id = deal_id
        policy_obj.save()
        updates.append((policy_obj.id, deal_id))

    monkeypatch.setattr("services.policies.update_policy", fake_update_policy)

    client = Client.create(name="Клиент")
    policy = Policy.create(
        client=client,
        policy_number="P-123",
        start_date=dt.date(2024, 1, 15),
    )

    view = PolicyTableView()
    monkeypatch.setattr(view, "get_selected_multiple", lambda: [policy])

    def fake_exec(self):
        self.save()
        return QDialog.Accepted

    monkeypatch.setattr("ui.forms.deal_form.DealForm.exec", fake_exec)

    view._on_make_deal()

    deal = Deal.select().first()
    assert deal is not None
    assert deal.status == "Автоматически созданная сделка"
    assert updates == [(policy.id, deal.id)]
