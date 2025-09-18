from __future__ import annotations

import datetime as dt

from PySide6.QtWidgets import QDialog

from database.models import Client, Deal, Policy
from services.policies.deal_matching import CandidateDeal
from ui.views.policy_table_view import PolicyTableView


def test_link_deal_prefills_candidates(monkeypatch, in_memory_db, qapp):
    monkeypatch.setattr(PolicyTableView, "load_data", lambda self: None)

    client = Client.create(name="Иванов")
    other_client = Client.create(name="Петров")

    candidate_deal = Deal.create(
        client=client,
        description="КАСКО",
        start_date=dt.date(2024, 1, 1),
    )
    manual_deal = Deal.create(
        client=other_client,
        description="ОСАГО",
        start_date=dt.date(2024, 2, 1),
    )

    policy_one = Policy.create(
        client=client,
        policy_number="P-001",
        start_date=dt.date(2024, 1, 5),
    )
    policy_two = Policy.create(
        client=client,
        policy_number="P-002",
        start_date=dt.date(2024, 1, 10),
    )

    view = PolicyTableView()
    monkeypatch.setattr(
        view,
        "get_selected_multiple",
        lambda: [policy_one, policy_two],
    )

    candidate = CandidateDeal(
        deal_id=candidate_deal.id,
        deal=candidate_deal,
        score=0.85,
        reasons=["совпал телефон", "есть полис с VIN TEST123"],
    )

    monkeypatch.setattr(
        "services.policies.find_candidate_deals",
        lambda policy, limit=10: [candidate],
    )
    monkeypatch.setattr(
        "services.deal_service.get_all_deals",
        lambda: [candidate_deal, manual_deal],
    )

    updates: list[tuple[int, int | None]] = []

    def fake_update_policy(policy_obj, deal_id=None, **kwargs):
        updates.append((policy_obj.id, deal_id))

    monkeypatch.setattr("services.policies.update_policy", fake_update_policy)

    class DummySearchDialog:
        auto_accept = True
        last_items: list[dict] | None = None

        def __init__(self, items, parent=None):
            self.items = items
            self.parent = parent
            self.selected_index = None
            DummySearchDialog.last_items = items

        def exec(self):
            if not DummySearchDialog.auto_accept or not self.items:
                return QDialog.Rejected
            self.selected_index = self.items[0]["value"]
            return QDialog.Accepted

    monkeypatch.setattr("ui.views.policy_table_view.SearchDialog", DummySearchDialog)

    view._on_link_deal()

    assert DummySearchDialog.last_items is not None
    first_item = DummySearchDialog.last_items[0]
    assert first_item["value"]["type"] == "candidate"
    assert first_item["label"].startswith("⭐ 0.85")
    assert "совпал телефон" in first_item["description"]

    manual_labels = [item["label"] for item in DummySearchDialog.last_items[1:]]
    assert any("Петров" in label for label in manual_labels)

    assert updates == [
        (policy_one.id, candidate_deal.id),
        (policy_two.id, candidate_deal.id),
    ]
