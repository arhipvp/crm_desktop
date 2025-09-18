from __future__ import annotations

import datetime as dt

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from database.models import Client, Deal, Policy
from services.policies.deal_matching import CandidateDeal
from ui.common.search_dialog import SearchDialog
from ui.views.policy_table_view import PolicyTableView


class DummySearchDialog:
    auto_accept = True
    last_items: list[dict] | None = None
    last_instance: "DummySearchDialog | None" = None

    def __init__(self, items, parent=None, make_deal_callback=None):
        self.items = items
        self.parent = parent
        self.selected_index = None
        self.make_deal_callback = make_deal_callback
        self.closed = False
        DummySearchDialog.last_items = items
        DummySearchDialog.last_instance = self

    def exec(self):
        if not DummySearchDialog.auto_accept or not self.items:
            return QDialog.Rejected
        self.selected_index = self.items[0]["value"]
        return QDialog.Accepted

    def trigger_make_deal(self):
        if self.make_deal_callback is not None:
            self.make_deal_callback()
            self.closed = True


def test_link_deal_prefills_candidates(monkeypatch, in_memory_db, qapp):
    monkeypatch.setattr(PolicyTableView, "load_data", lambda self: None)
    DummySearchDialog.auto_accept = True
    DummySearchDialog.last_items = None
    DummySearchDialog.last_instance = None

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

    def fake_candidates(policy, limit=10):
        del policy, limit
        return [
            CandidateDeal(
                deal_id=candidate_deal.id,
                deal=candidate_deal,
                score=0.85,
                reasons=["совпал телефон", "есть полис с VIN TEST123"],
            )
        ]

    monkeypatch.setattr(
        "services.policies.find_candidate_deals",
        fake_candidates,
    )
    monkeypatch.setattr(
        "services.deal_service.get_all_deals",
        lambda: [candidate_deal, manual_deal],
    )

    updates: list[tuple[int, int | None]] = []

    def fake_update_policy(policy_obj, deal_id=None, **kwargs):
        updates.append((policy_obj.id, deal_id))

    monkeypatch.setattr("services.policies.update_policy", fake_update_policy)

    monkeypatch.setattr("ui.views.policy_table_view.SearchDialog", DummySearchDialog)

    view._on_link_deal()

    assert DummySearchDialog.last_items is not None
    first_item = DummySearchDialog.last_items[0]
    assert first_item["value"]["type"] == "candidate"
    assert first_item["score"] == 0.85 * 2
    assert first_item["title"] == "Иванов"
    assert first_item["subtitle"] == "КАСКО"
    assert "совпал телефон" in first_item["comment"]
    assert "⚠️" not in first_item["comment"]
    assert len(first_item["details"]) == 2
    assert all(detail.startswith("Полис ") for detail in first_item["details"])
    assert any("P-001" in detail for detail in first_item["details"])
    assert any("P-002" in detail for detail in first_item["details"])
    assert first_item["value"]["unsupported_policy_ids"] == []

    manual_labels = [item["title"] for item in DummySearchDialog.last_items[1:]]
    assert any("Петров" in label for label in manual_labels)
    manual_details = [item["details"] for item in DummySearchDialog.last_items[1:]]
    assert all(details == [] for details in manual_details)

    assert updates == [
        (policy_one.id, candidate_deal.id),
        (policy_two.id, candidate_deal.id),
    ]


def test_link_deal_conflicting_candidates_require_confirmation(
    monkeypatch, in_memory_db, qapp
):
    monkeypatch.setattr(PolicyTableView, "load_data", lambda self: None)

    client = Client.create(name="Иванов")

    deal_a = Deal.create(
        client=client,
        description="Сделка A",
        start_date=dt.date(2024, 4, 1),
    )
    deal_b = Deal.create(
        client=client,
        description="Сделка B",
        start_date=dt.date(2024, 5, 1),
    )

    policy_a = Policy.create(
        client=client,
        policy_number="PA-001",
        start_date=dt.date(2024, 4, 5),
    )
    policy_b = Policy.create(
        client=client,
        policy_number="PB-002",
        start_date=dt.date(2024, 5, 10),
    )

    view = PolicyTableView()
    monkeypatch.setattr(
        view,
        "get_selected_multiple",
        lambda: [policy_a, policy_b],
    )

    def fake_candidates(policy, limit=10):
        del limit
        if policy.id == policy_a.id:
            return [
                CandidateDeal(
                    deal_id=deal_a.id,
                    deal=deal_a,
                    score=0.9,
                    reasons=["VIN совпал"],
                )
            ]
        return [
            CandidateDeal(
                deal_id=deal_b.id,
                deal=deal_b,
                score=0.8,
                reasons=["телефон клиента"],
            )
        ]

    monkeypatch.setattr(
        "services.policies.find_candidate_deals",
        fake_candidates,
    )
    monkeypatch.setattr(
        "services.deal_service.get_all_deals",
        lambda: [deal_a, deal_b],
    )

    updates: list[tuple[int, int | None]] = []

    def fake_update_policy(policy_obj, deal_id=None, **kwargs):
        del kwargs
        updates.append((policy_obj.id, deal_id))

    monkeypatch.setattr("services.policies.update_policy", fake_update_policy)

    confirm_messages: list[str] = []

    def fake_confirm(message):
        confirm_messages.append(message)
        return False

    monkeypatch.setattr("ui.views.policy_table_view.confirm", fake_confirm)

    DummySearchDialog.auto_accept = True
    DummySearchDialog.last_items = None
    monkeypatch.setattr("ui.views.policy_table_view.SearchDialog", DummySearchDialog)

    view._on_link_deal()

    assert DummySearchDialog.last_items is not None
    first_item = DummySearchDialog.last_items[0]
    assert first_item["value"]["type"] == "candidate"
    assert "⚠️" in first_item["comment"]
    assert any("⚠️" in detail for detail in first_item["details"])
    assert first_item["value"]["unsupported_policy_ids"] == [policy_b.id]

    assert confirm_messages
    assert "PB-002" in confirm_messages[0]
    assert updates == []


def test_link_deal_make_deal_button_triggers_callback(
    monkeypatch, in_memory_db, qapp
):
    monkeypatch.setattr(PolicyTableView, "load_data", lambda self: None)

    client = Client.create(name="Иванов")
    deal = Deal.create(
        client=client,
        description="КАСКО",
        start_date=dt.date(2024, 1, 1),
    )
    policy = Policy.create(
        client=client,
        policy_number="P-003",
        start_date=dt.date(2024, 3, 1),
    )

    view = PolicyTableView()
    monkeypatch.setattr(view, "get_selected_multiple", lambda: [policy])

    monkeypatch.setattr(
        "services.policies.find_candidate_deals",
        lambda policy, limit=10: [],
    )
    monkeypatch.setattr(
        "services.deal_service.get_all_deals",
        lambda: [deal],
    )

    called = []
    monkeypatch.setattr(view, "_on_make_deal", lambda: called.append(True))

    DummySearchDialog.auto_accept = False
    DummySearchDialog.last_instance = None
    monkeypatch.setattr("ui.views.policy_table_view.SearchDialog", DummySearchDialog)

    view._on_link_deal()

    dlg_instance = DummySearchDialog.last_instance
    assert dlg_instance is not None
    assert dlg_instance.make_deal_callback is not None

    dlg_instance.trigger_make_deal()

    assert called == [True]

    DummySearchDialog.auto_accept = True


def test_search_dialog_displays_candidate_details(qapp):
    candidate_reasons = ["совпал телефон", "есть полис с VIN TEST123"]
    items = [
        {
            "score": 0.85,
            "title": "Иванов",
            "subtitle": "",
            "comment": "; ".join(candidate_reasons),
            "value": {"type": "candidate"},
            "details": candidate_reasons,
        },
        {
            "score": None,
            "title": "Петров",
            "subtitle": "ОСАГО",
            "comment": "",
            "value": {"type": "manual"},
            "details": [],
        },
    ]

    dlg = SearchDialog(items)
    try:
        qapp.processEvents()
        assert dlg.filtered_items[0]["details"] == candidate_reasons

        candidate_text = dlg.detail_view.toPlainText()
        assert "совпал телефон" in candidate_text
        assert "есть полис с VIN TEST123" in candidate_text

        dlg.table_view.selectRow(1)
        qapp.processEvents()
        manual_text = dlg.detail_view.toPlainText()
        assert "Причин нет — ручной выбор" in manual_text
    finally:
        dlg.close()


def test_search_dialog_score_sorting(qapp):
    items = [
        {
            "score": 0.5,
            "title": "Клиент A",
            "subtitle": "",
            "comment": "",
            "value": {"type": "candidate", "id": "A"},
            "details": ["детали A"],
        },
        {
            "score": 0.9,
            "title": "Клиент B",
            "subtitle": "",
            "comment": "",
            "value": {"type": "candidate", "id": "B"},
            "details": ["детали B"],
        },
        {
            "score": 0.75,
            "title": "Клиент C",
            "subtitle": "",
            "comment": "",
            "value": {"type": "candidate", "id": "C"},
            "details": ["детали C"],
        },
    ]

    dlg = SearchDialog(items)
    try:
        qapp.processEvents()
        first_item = dlg.model.item(0, 0)
        assert first_item.data(Qt.DisplayRole) == "0.50"
        assert isinstance(first_item.data(Qt.UserRole), float)

        dlg.table_view.sortByColumn(0, Qt.DescendingOrder)
        qapp.processEvents()
        sorted_scores = [
            dlg.model.item(row, 0).data(Qt.UserRole)
            for row in range(dlg.model.rowCount())
        ]
        assert sorted_scores == sorted(sorted_scores, reverse=True)

        top_index = dlg.model.index(0, 0)
        dlg.table_view.setCurrentIndex(top_index)
        dlg.table_view.selectRow(0)
        qapp.processEvents()
        dlg._apply_selection(top_index)

        top_item = dlg.model.item(0, 0).data(Qt.UserRole + 1)
        assert isinstance(top_item, dict)
        assert top_item["value"]["id"] == "B"
        assert dlg.selected_index == top_item["value"]

        details_text = dlg.detail_view.toPlainText()
        assert "детали B" in details_text
    finally:
        dlg.close()
