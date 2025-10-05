from datetime import date
from pathlib import Path

from dateutil.relativedelta import relativedelta

from database.models import Client, Deal, Policy
from services.deals.deal_app_service import DealAppService
from services.deal_service import (
    add_deal_from_policy,
    add_deal_from_policies,
    get_open_deals,
    update_deal,
)
from services.folder_utils import sanitize_name
from utils.filter_constants import CHOICE_NULL_TOKEN


def test_add_deal_from_policy_sets_reminder_date(
    in_memory_db, stub_drive_gateway
):
    client = Client.create(name="Клиент")
    start_date = date(2024, 1, 15)
    policy = Policy.create(
        client=client,
        policy_number="P-123",
        start_date=start_date,
    )

    deal = add_deal_from_policy(policy, gateway=stub_drive_gateway)

    assert deal.reminder_date == start_date + relativedelta(months=9)


def test_add_deal_from_policy_moves_folder(in_memory_db, stub_drive_gateway):
    client = Client.create(name="Клиент")
    policy_folder = stub_drive_gateway.local_root / "policy_folder"
    policy_folder.mkdir()

    policy = Policy.create(
        client=client,
        policy_number="P-123",
        start_date=date(2024, 1, 15),
        drive_folder_path=str(policy_folder),
    )

    deal = add_deal_from_policy(policy, gateway=stub_drive_gateway)

    updated_policy = Policy.get_by_id(policy.id)
    expected_base = (
        Path(stub_drive_gateway.local_root)
        / sanitize_name(client.name)
        / sanitize_name(f"Сделка - Из полиса {policy.policy_number}")
    )
    expected_path = expected_base / policy_folder.name

    assert expected_path.is_dir()
    assert updated_policy.drive_folder_path == str(expected_path)
    assert not policy_folder.exists()
    assert deal.drive_folder_path == str(expected_base)


def test_add_deal_from_policies_moves_all_folders(in_memory_db, stub_drive_gateway):
    client = Client.create(name="Клиент")
    folder_one = stub_drive_gateway.local_root / "policy_one"
    folder_two = stub_drive_gateway.local_root / "policy_two"
    folder_one.mkdir()
    folder_two.mkdir()

    policy_one = Policy.create(
        client=client,
        policy_number="P-001",
        start_date=date(2024, 1, 10),
        drive_folder_path=str(folder_one),
    )
    policy_two = Policy.create(
        client=client,
        policy_number="P-002",
        start_date=date(2024, 2, 10),
        drive_folder_path=str(folder_two),
    )

    deal = add_deal_from_policies(
        [policy_one, policy_two], gateway=stub_drive_gateway
    )

    updated_one = Policy.get_by_id(policy_one.id)
    updated_two = Policy.get_by_id(policy_two.id)
    expected_base = (
        Path(stub_drive_gateway.local_root)
        / sanitize_name(client.name)
        / sanitize_name(f"Сделка - Из полиса {policy_one.policy_number}")
    )
    expected_one = expected_base / folder_one.name
    expected_two = expected_base / folder_two.name

    assert expected_one.is_dir()
    assert expected_two.is_dir()
    assert updated_one.drive_folder_path == str(expected_one)
    assert updated_two.drive_folder_path == str(expected_two)
    assert not folder_one.exists()
    assert not folder_two.exists()
    assert deal.drive_folder_path == str(expected_base)


def test_update_deal_reopen_clears_closed_reason(in_memory_db):
    client = Client.create(name="Клиент")
    deal = Deal.create(
        client=client,
        description="Закрытая сделка",
        start_date=date(2024, 5, 1),
        is_closed=True,
        closed_reason="Нет интереса",
    )

    update_deal(deal, is_closed=False, closed_reason=None)

    reopened = Deal.get_by_id(deal.id)
    assert reopened.is_closed is False
    assert reopened.closed_reason is None

    open_ids = {d.id for d in get_open_deals()}
    assert deal.id in open_ids


def test_deal_app_service_filters_null_closed_reason(in_memory_db):
    client = Client.create(name="Фильтр")
    deal_without_reason = Deal.create(
        client=client,
        description="Без причины",
        start_date=date(2024, 6, 1),
        closed_reason=None,
    )
    deal_with_reason = Deal.create(
        client=client,
        description="С причиной",
        start_date=date(2024, 6, 2),
        closed_reason="Отказ",
    )

    service = DealAppService()

    rows, total = service.get_page(
        1,
        20,
        column_filters={"closed_reason": [CHOICE_NULL_TOKEN]},
    )
    assert total == 1
    assert {row.id for row in rows} == {deal_without_reason.id}

    mixed_rows, mixed_total = service.get_page(
        1,
        20,
        column_filters={"closed_reason": [CHOICE_NULL_TOKEN, "Отказ"]},
    )
    assert mixed_total == 2
    assert {row.id for row in mixed_rows} == {
        deal_without_reason.id,
        deal_with_reason.id,
    }
