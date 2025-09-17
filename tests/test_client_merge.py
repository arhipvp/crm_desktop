import datetime

import pytest

from database.models import Client, Deal, Policy
from services.clients.client_service import (
    ClientMergeError,
    merge_clients,
)


@pytest.mark.usefixtures("in_memory_db")
def test_merge_clients_transfers_relations_and_updates_fields(monkeypatch):
    primary = Client.create(
        name="Primary Client",
        note="Primary note",
        email=None,
        phone=None,
        drive_folder_path="primary/path",
        drive_folder_link="primary/link",
    )

    duplicate_one = Client.create(
        name="Duplicate One",
        note="Duplicate note 1",
        email="duplicate1@example.com",
        phone=None,
        drive_folder_path="dup1/path",
        drive_folder_link="dup1/link",
    )
    duplicate_two = Client.create(
        name="Duplicate Two",
        note="Duplicate note 2",
        email=None,
        phone="9112223344",
        drive_folder_path="dup2/path",
        drive_folder_link="dup2/link",
    )

    deal_one = Deal.create(
        client=duplicate_one,
        description="First Deal",
        start_date=datetime.date.today(),
        drive_folder_path="deal1/path",
        drive_folder_link="deal1/link",
    )
    deal_two = Deal.create(
        client=duplicate_two,
        description="Second Deal",
        start_date=datetime.date.today(),
        drive_folder_path="deal2/path",
        drive_folder_link="deal2/link",
    )

    policy_one = Policy.create(
        client=duplicate_one,
        deal=deal_one,
        policy_number="POLICY-1",
        start_date=datetime.date.today(),
        drive_folder_link="policy1/link",
    )
    policy_two = Policy.create(
        client=duplicate_two,
        deal=deal_two,
        policy_number="POLICY-2",
        start_date=datetime.date.today(),
        drive_folder_link="policy2/link",
    )

    deal_rename_calls: list[tuple] = []
    policy_rename_calls: list[tuple] = []

    def fake_rename_deal_folder(
        old_client_name,
        old_description,
        new_client_name,
        new_description,
        drive_link,
        current_path,
    ):
        deal_rename_calls.append(
            (
                old_client_name,
                old_description,
                new_client_name,
                new_description,
                drive_link,
                current_path,
            )
        )
        return (f"/renamed/deal/{old_description}", f"https://deal/{old_description}")

    def fake_rename_policy_folder(
        old_client_name,
        old_policy_number,
        old_deal_desc,
        new_client_name,
        new_policy_number,
        new_deal_desc,
        drive_link,
    ):
        policy_rename_calls.append(
            (
                old_client_name,
                old_policy_number,
                old_deal_desc,
                new_client_name,
                new_policy_number,
                new_deal_desc,
                drive_link,
            )
        )
        return (f"https://policy/{old_policy_number}", None)

    monkeypatch.setattr(
        "services.clients.client_service.rename_deal_folder", fake_rename_deal_folder
    )
    monkeypatch.setattr(
        "services.clients.client_service.rename_policy_folder", fake_rename_policy_folder
    )

    merge_clients(primary.id, [duplicate_one.id, duplicate_two.id])

    updated_primary = Client.get_by_id(primary.id)
    assert updated_primary.email == "duplicate1@example.com"
    assert updated_primary.phone == "+79112223344"
    assert (
        updated_primary.note
        == "Primary note\n\nDuplicate note 1\n\nDuplicate note 2"
    )

    updated_deal_one = Deal.get_by_id(deal_one.id)
    updated_deal_two = Deal.get_by_id(deal_two.id)
    assert updated_deal_one.client_id == primary.id
    assert updated_deal_two.client_id == primary.id
    assert updated_deal_one.drive_folder_path == "/renamed/deal/First Deal"
    assert updated_deal_one.drive_folder_link == "https://deal/First Deal"
    assert updated_deal_two.drive_folder_path == "/renamed/deal/Second Deal"
    assert updated_deal_two.drive_folder_link == "https://deal/Second Deal"

    updated_policy_one = Policy.get_by_id(policy_one.id)
    updated_policy_two = Policy.get_by_id(policy_two.id)
    assert updated_policy_one.client_id == primary.id
    assert updated_policy_two.client_id == primary.id
    assert updated_policy_one.deal_id == deal_one.id
    assert updated_policy_two.deal_id == deal_two.id
    assert updated_policy_one.deal.client_id == primary.id
    assert updated_policy_two.deal.client_id == primary.id
    assert updated_policy_one.drive_folder_link == "https://policy/POLICY-1"
    assert updated_policy_two.drive_folder_link == "https://policy/POLICY-2"

    updated_duplicate_one = Client.get_by_id(duplicate_one.id)
    updated_duplicate_two = Client.get_by_id(duplicate_two.id)
    assert updated_duplicate_one.is_deleted is True
    assert updated_duplicate_two.is_deleted is True
    assert updated_duplicate_one.drive_folder_path is None
    assert updated_duplicate_two.drive_folder_path is None
    assert updated_duplicate_one.drive_folder_link is None
    assert updated_duplicate_two.drive_folder_link is None

    assert deal_rename_calls == [
        (
            "Duplicate One",
            "First Deal",
            "Primary Client",
            "First Deal",
            "deal1/link",
            "deal1/path",
        ),
        (
            "Duplicate Two",
            "Second Deal",
            "Primary Client",
            "Second Deal",
            "deal2/link",
            "deal2/path",
        ),
    ]
    assert policy_rename_calls == [
        (
            "Duplicate One",
            "POLICY-1",
            "First Deal",
            "Primary Client",
            "POLICY-1",
            "First Deal",
            "policy1/link",
        ),
        (
            "Duplicate Two",
            "POLICY-2",
            "Second Deal",
            "Primary Client",
            "POLICY-2",
            "Second Deal",
            "policy2/link",
        ),
    ]


@pytest.mark.usefixtures("in_memory_db")
def test_merge_clients_requires_duplicates():
    client = Client.create(name="Solo")

    with pytest.raises(ClientMergeError, match="Список дубликатов пуст"):
        merge_clients(client.id, [])


@pytest.mark.usefixtures("in_memory_db")
def test_merge_clients_rejects_primary_in_duplicates():
    primary = Client.create(name="Primary")
    duplicate = Client.create(name="Duplicate")

    with pytest.raises(
        ClientMergeError, match="Список дубликатов не должен содержать основной id"
    ):
        merge_clients(primary.id, [duplicate.id, primary.id])


@pytest.mark.usefixtures("in_memory_db")
def test_merge_clients_missing_ids():
    primary = Client.create(name="Primary")
    missing_id = primary.id + 1

    with pytest.raises(ClientMergeError, match="Не найдены клиенты с id"):
        merge_clients(primary.id, [missing_id])
