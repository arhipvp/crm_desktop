from datetime import date

import pytest

from database.models import Client, Deal, Policy
from services.policies import build_deal_match_index, make_policy_profile
from services.policies.deal_matching import collect_indirect_matches, find_strict_matches


@pytest.mark.usefixtures("in_memory_db")
def test_find_strict_matches_by_vin():
    client = Client.create(name="Client")
    deal = Deal.create(
        client=client,
        description="Оформление полиса",
        start_date=date(2024, 1, 1),
    )
    matched_policy = Policy.create(
        client=client,
        deal=deal,
        policy_number="VIN-001",
        start_date=date(2024, 1, 10),
        vehicle_vin="XW8-1234-5678",
    )
    candidate_policy = Policy.create(
        client=client,
        deal=None,
        policy_number="NEW-100",
        start_date=date(2024, 2, 1),
        vehicle_vin="xw8 1234 5678",
    )

    deal_index = build_deal_match_index([deal.id])
    policy_profile = make_policy_profile(candidate_policy)

    matches = find_strict_matches(policy_profile, deal_index)

    assert len(matches) == 1
    candidate = matches[0]
    assert candidate.deal_id == deal.id
    assert candidate.score == 1.0
    assert candidate.reasons == [
        f"VIN совпадает с полисом №{matched_policy.policy_number}"
    ]


@pytest.mark.usefixtures("in_memory_db")
def test_find_strict_matches_by_policy_number_in_description():
    client = Client.create(name="Client")
    deal = Deal.create(
        client=client,
        description="Полис AB-12345 находится в работе",
        start_date=date(2024, 1, 1),
    )
    Policy.create(
        client=client,
        deal=deal,
        policy_number="EXIST-001",
        start_date=date(2024, 1, 10),
    )
    candidate_policy = Policy.create(
        client=client,
        deal=None,
        policy_number="AB 12345",
        start_date=date(2024, 2, 1),
    )

    deal_index = build_deal_match_index([deal.id])
    policy_profile = make_policy_profile(candidate_policy)

    matches = find_strict_matches(policy_profile, deal_index)

    assert len(matches) == 1
    candidate = matches[0]
    assert candidate.deal_id == deal.id
    assert candidate.reasons == [
        f"Номер полиса {candidate_policy.policy_number} найден в описании сделки"
    ]


@pytest.mark.usefixtures("in_memory_db")
def test_find_strict_matches_by_drive_folder():
    client = Client.create(name="Client")
    deal = Deal.create(
        client=client,
        description="Полис без номера",
        start_date=date(2024, 1, 1),
        drive_folder_path="clients/deal",
    )
    Policy.create(
        client=client,
        deal=deal,
        policy_number="POL-001",
        start_date=date(2024, 1, 10),
    )
    candidate_policy = Policy.create(
        client=client,
        deal=None,
        policy_number="POL-NEW",
        start_date=date(2024, 2, 1),
        drive_folder_link="clients/deal/policies/new",
    )

    deal_index = build_deal_match_index([deal.id])
    policy_profile = make_policy_profile(candidate_policy)

    matches = find_strict_matches(policy_profile, deal_index)

    assert len(matches) == 1
    candidate = matches[0]
    assert candidate.deal_id == deal.id
    assert candidate.reasons == [
        "Ссылка на диск полиса вложена в папку сделки"
    ]


@pytest.mark.usefixtures("in_memory_db")
def test_collect_indirect_matches_by_phone():
    deal_client = Client.create(
        name="ООО Клиент",
        phone="+7 (999) 123-45-67",
    )
    other_client = Client.create(
        name="ООО Другая Компания",
        phone="+7 999 123 45 67",
    )
    deal = Deal.create(
        client=deal_client,
        description="Оформление полиса",
        start_date=date(2024, 1, 1),
    )
    Policy.create(
        client=deal_client,
        deal=deal,
        policy_number="EXIST-001",
        start_date=date(2024, 1, 10),
    )
    candidate_policy = Policy.create(
        client=other_client,
        deal=None,
        policy_number="NEW-100",
        start_date=date(2024, 2, 1),
    )

    deal_index = build_deal_match_index([deal.id])
    policy_profile = make_policy_profile(candidate_policy)

    matches = collect_indirect_matches(policy_profile, deal_index)

    assert len(matches) == 1
    match = matches[0]
    assert match.deal_id == deal.id
    assert match.score == 0.6
    assert match.reasons == ["Совпадает телефон клиента: 79991234567"]


@pytest.mark.usefixtures("in_memory_db")
def test_collect_indirect_matches_by_contractor_similarity():
    deal_client = Client.create(
        name="ИП Иванов",
        phone="+7 (911) 000-00-00",
    )
    other_client = Client.create(
        name="ООО Зета",
        phone="+7 (922) 111-11-11",
    )
    deal = Deal.create(
        client=deal_client,
        description="Оформление полиса",
        start_date=date(2024, 1, 1),
    )
    Policy.create(
        client=deal_client,
        deal=deal,
        policy_number="EXIST-002",
        start_date=date(2024, 1, 15),
        contractor="ООО Альфа",
    )
    candidate_policy = Policy.create(
        client=other_client,
        deal=None,
        policy_number="NEW-200",
        start_date=date(2024, 2, 1),
        contractor="ООО Альфа",
    )

    deal_index = build_deal_match_index([deal.id])
    policy_profile = make_policy_profile(candidate_policy)

    matches = collect_indirect_matches(policy_profile, deal_index)

    assert len(matches) == 1
    match = matches[0]
    assert match.deal_id == deal.id
    assert match.score == 0.5
    assert match.reasons == [
        "Контрагент полиса похож на контрагента сделки (совпадение 1.00)"
    ]
