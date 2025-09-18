import logging
from datetime import date

import pytest

from database.models import Client, Deal, Policy
from services.policies import find_candidate_deals
from services.policies.deal_matching import (
    BRAND_MODEL_DATE_WEIGHT,
    EMAIL_MATCH_WEIGHT,
    build_deal_match_index,
    find_candidate_deal_ids,
)


@pytest.mark.usefixtures("in_memory_db")
def test_find_candidate_deals_orders_and_merges(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="services.policies.deal_matching")

    strict_client = Client.create(
        name="ООО Альфа",
        phone="+7 (900) 111-22-33",
        email="alpha@example.com",
        drive_folder_path="clients/alpha/deal",
    )
    deal_strict = Deal.create(
        client=strict_client,
        description="Оформление полиса",
        start_date=date(2024, 1, 1),
        drive_folder_path="clients/alpha/deal",
    )
    existing_policy = Policy.create(
        client=strict_client,
        deal=deal_strict,
        policy_number="VIN-EXIST",
        start_date=date(2024, 1, 10),
        vehicle_vin="XW8-1234-5678",
    )

    email_client = Client.create(
        name="ООО Гамма",
        phone="+7 (901) 333-44-55",
        email="shared@example.com",
    )
    deal_email = Deal.create(
        client=email_client,
        description="Продление полиса",
        start_date=date(2024, 1, 5),
    )

    brand_client = Client.create(
        name="ИП Петров",
        phone="+7 (902) 666-77-88",
    )
    deal_brand = Deal.create(
        client=brand_client,
        description="Корпоративный автопарк",
        start_date=date(2024, 1, 15),
    )
    Policy.create(
        client=brand_client,
        deal=deal_brand,
        policy_number="BRAND-001",
        start_date=date(2024, 1, 20),
        end_date=date(2024, 7, 20),
        vehicle_brand="Toyota",
        vehicle_model="Camry",
    )

    candidate_client = Client.create(
        name="ООО Бета",
        phone="+7 900 111 22 33",
        email="shared@example.com",
    )
    candidate_policy = Policy.create(
        client=candidate_client,
        deal=None,
        policy_number="NEW-999",
        start_date=date(2024, 2, 1),
        vehicle_vin="xw812345678",
        vehicle_brand="Toyota",
        vehicle_model="Camry",
        insurance_company="ВСК",
        insurance_type="КАСКО",
        sales_channel="Онлайн",
    )

    expected_candidates = {deal_strict.id, deal_email.id, deal_brand.id}
    assert find_candidate_deal_ids(candidate_policy) == expected_candidates

    original_build = build_deal_match_index
    captured_calls: list[set[int] | None] = []

    def fake_build(ids=None):
        captured_calls.append(None if ids is None else set(ids))
        return original_build(ids)

    monkeypatch.setattr(
        "services.policies.deal_matching.build_deal_match_index",
        fake_build,
    )

    candidates = find_candidate_deals(candidate_policy, limit=5)

    assert [candidate.deal_id for candidate in candidates] == [
        deal_strict.id,
        deal_email.id,
        deal_brand.id,
    ]

    strict_candidate = candidates[0]
    expected_phone = "".join(filter(str.isdigit, strict_client.phone))
    assert strict_candidate.deal == deal_strict
    assert strict_candidate.score == 1.0
    assert strict_candidate.reasons == [
        f"VIN совпадает с полисом №{existing_policy.policy_number}",
        f"Совпадает телефон клиента: {expected_phone}",
    ]

    email_candidate = candidates[1]
    assert email_candidate.deal == deal_email
    assert email_candidate.score == EMAIL_MATCH_WEIGHT
    assert email_candidate.reasons == [
        "Совпадает email клиента: shared@example.com",
    ]

    brand_candidate = candidates[2]
    assert brand_candidate.deal == deal_brand
    assert brand_candidate.score == BRAND_MODEL_DATE_WEIGHT
    assert brand_candidate.reasons == [
        "Совпадают марка и модель без совпадения VIN (Toyota / Camry)",
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

