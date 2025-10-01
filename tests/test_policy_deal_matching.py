import logging
from datetime import date
from types import SimpleNamespace

import pytest

from database.models import Client, Deal, Expense, Payment, Policy
from services.policies import find_candidate_deals
from services.policies.deal_matching import (
    BRAND_MODEL_DATE_WEIGHT,
    EMAIL_MATCH_WEIGHT,
    CandidateDeal,
    build_deal_match_index,
    find_candidate_deal_ids,
)


def test_find_candidate_deals_orders_and_merges(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="services.policies.deal_matching")

    policy = SimpleNamespace(policy_number="NEW-999")

    expected_candidates = {1, 2, 3}
    deal_index = {
        deal_id: SimpleNamespace(deal=SimpleNamespace(id=deal_id))
        for deal_id in expected_candidates
    }
    captured_calls: list[set[int] | None] = []

    strict_matches = [
        CandidateDeal(
            deal_id=1,
            score=0.4,
            reasons=["VIN совпадает"],
            is_strict=True,
        ),
        CandidateDeal(
            deal_id=2,
            score=0.4,
            reasons=["VIN совпадает"],
            is_strict=True,
        ),
    ]
    indirect_matches = [
        CandidateDeal(
            deal_id=1,
            score=0.5,
            reasons=["Совпадает email"],
        ),
        CandidateDeal(
            deal_id=2,
            score=0.5,
            reasons=["Совпадает email", "VIN совпадает"],
        ),
        CandidateDeal(
            deal_id=3,
            score=0.9,
            reasons=["Совпадают марка и модель", "Совпадают марка и модель"],
        ),
    ]

    monkeypatch.setattr(
        "services.policies.deal_matching.find_candidate_deal_ids",
        lambda _: expected_candidates,
    )
    monkeypatch.setattr(
        "services.policies.deal_matching.build_deal_match_index",
        lambda ids=None: captured_calls.append(
            None if ids is None else set(ids)
        ) or deal_index,
    )
    monkeypatch.setattr(
        "services.policies.deal_matching.make_policy_profile",
        lambda _: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "services.policies.deal_matching.find_strict_matches",
        lambda _policy, _index: strict_matches,
    )
    monkeypatch.setattr(
        "services.policies.deal_matching.collect_indirect_matches",
        lambda _policy, _index: indirect_matches,
    )

    candidates = find_candidate_deals(policy, limit=5)

    assert [candidate.deal_id for candidate in candidates] == [1, 2, 3]
    assert [candidate.score for candidate in candidates] == [0.9, 0.9, 0.9]
    assert [candidate.is_strict for candidate in candidates] == [
        True,
        True,
        False,
    ]
    assert [candidate.reasons for candidate in candidates] == [
        ["VIN совпадает", "Совпадает email"],
        ["VIN совпадает", "Совпадает email"],
        ["Совпадают марка и модель"],
    ]

    logged_reasons = [
        record.args[3]
        for record in caplog.records
        if record.levelno == logging.INFO
        and record.name == "services.policies.deal_matching"
    ]
    assert logged_reasons == [candidate.reasons[:3] for candidate in candidates]

    assert captured_calls == [expected_candidates]


@pytest.mark.usefixtures("in_memory_db")
def test_find_candidate_deal_ids_matches_phone_with_eight_prefix():
    deal_client = Client.create(
        name="ООО Телефон", phone="8 (905) 123-45-67", email="phone@example.com"
    )
    deal = Deal.create(
        client=deal_client,
        description="Страхование автомобиля",
        start_date=date(2024, 5, 1),
    )

    policy_client = Client.create(
        name="ООО Телефон Полис",
        phone="+7 905 123 45 67",
        email="policy-phone@example.com",
    )
    policy = Policy.create(
        client=policy_client,
        deal=None,
        policy_number="PHONE-001",
        start_date=date(2024, 6, 1),
    )

    assert find_candidate_deal_ids(policy) == {deal.id}


@pytest.mark.usefixtures("in_memory_db")
def test_find_candidate_deal_ids_matches_contractor_with_expense():
    client = Client.create(name="ООО Заказчик")
    deal = Deal.create(
        client=client,
        description="Сделка с подрядчиком",
        start_date=date(2024, 5, 15),
    )
    matched_policy = Policy.create(
        client=client,
        deal=deal,
        policy_number="CONTRACTOR-001",
        start_date=date(2024, 5, 20),
        contractor="Acme Contractor",
    )
    payment = Payment.create(
        policy=matched_policy,
        amount=1000,
        payment_date=date(2024, 5, 21),
    )
    Expense.create(
        policy=matched_policy,
        payment=payment,
        amount=500,
        expense_type="commission",
    )

    candidate_client = Client.create(name="ООО Новый Клиент")
    candidate_policy = Policy.create(
        client=candidate_client,
        deal=None,
        policy_number="CONTRACTOR-NEW",
        start_date=date(2024, 6, 1),
        contractor="  acme contractor  ",
    )

    assert find_candidate_deal_ids(candidate_policy) == {deal.id}


@pytest.mark.usefixtures("in_memory_db")
def test_find_candidate_deals_fallback_without_candidates(monkeypatch):
    unrelated_client = Client.create(name="ООО Дельта")
    Deal.create(
        client=unrelated_client,
        description="Несвязанная сделка",
        start_date=date(2024, 3, 1),
    )

    policy_client = Client.create(name="ООО Эпсилон")
    candidate_policy = Policy.create(
        client=policy_client,
        deal=None,
        policy_number="UNIQ-42",
        start_date=date(2024, 4, 1),
    )

    assert find_candidate_deal_ids(candidate_policy) is None

    original_build = build_deal_match_index
    captured_calls: list[set[int] | None] = []

    def fake_build(ids=None):
        captured_calls.append(None if ids is None else set(ids))
        return original_build(ids)

    monkeypatch.setattr(
        "services.policies.deal_matching.build_deal_match_index",
        fake_build,
    )

    assert find_candidate_deals(candidate_policy, limit=5) == []
    assert captured_calls == [None]

