from datetime import date

import pytest

from database.models import Client, Deal, Policy
from services.policies import build_deal_match_index, make_policy_profile


@pytest.mark.usefixtures("in_memory_db")
def test_make_policy_profile_normalizes_values():
    client = Client.create(name="Client")
    deal = Deal.create(
        client=client,
        description="Test",
        start_date=date(2024, 1, 1),
    )
    policy = Policy.create(
        client=client,
        deal=deal,
        policy_number="  AB-12345  ",
        start_date=date(2024, 1, 10),
        end_date=date(2024, 5, 10),
        vehicle_vin=" 1HG-CM82633A 004352 ",
        contractor=" ООО Контрагент ",
    )

    profile = make_policy_profile(policy)

    assert profile.normalized_policy_number == "ab-12345"
    assert profile.normalized_vehicle_vin == "1hgcm82633a004352"
    assert profile.normalized_contractor == "ооо контрагент"


@pytest.mark.usefixtures("in_memory_db")
def test_build_deal_match_index_collects_normalized_features():
    client = Client.create(
        name="Client",
        phone=" +7 (999) 123-45-67 ",
        email=" Test@Example.COM ",
        drive_folder_path=" client/folder ",
    )
    deal = Deal.create(
        client=client,
        description="Test",
        start_date=date(2024, 1, 1),
        drive_folder_path=" deal/folder ",
        drive_folder_link=" https://deal/link ",
    )
    Policy.create(
        client=client,
        deal=deal,
        policy_number="  AB-12345  ",
        start_date=date(2024, 1, 10),
        end_date=date(2024, 5, 10),
        vehicle_vin=" 1HG-CM82633A 004352 ",
        contractor=" ООО Контрагент ",
        drive_folder_link=" https://policy/one ",
    )
    Policy.create(
        client=client,
        deal=deal,
        policy_number=" CD-67890 ",
        start_date=date(2024, 2, 5),
        end_date=date(2024, 12, 31),
        contractor=" Второй Контрагент ",
    )

    index = build_deal_match_index([deal.id])

    assert deal.id in index
    profile = index[deal.id]

    assert profile.vins == {"1hgcm82633a004352"}
    assert profile.client_phones == {"79991234567"}
    assert profile.contractors == {"ооо контрагент", "второй контрагент"}
    assert profile.policy_date_range == (date(2024, 1, 10), date(2024, 12, 31))
    assert profile.folder_paths == {
        "deal/folder",
        "https://deal/link",
        "client/folder",
        "https://policy/one",
    }
    assert profile.client_emails == {"test@example.com"}
