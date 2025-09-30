import datetime
from types import SimpleNamespace

import logging
import openai
import pytest

from config import Settings
from database.db import db
from database.models import Client, Policy, Payment, Deal
from services.policies import policy_service as ps, ai_policy_service
from services.policies.ai_policy_service import _chat
from services.payment_service import add_payment


@pytest.fixture()
def fake_drive_gateway():
    class FakeDriveGateway:
        pass

    return FakeDriveGateway()
def test_policy_merge_additional_payments(
    in_memory_db, policy_folder_patches, fake_drive_gateway
):
    client = Client.create(name='C')
    start = datetime.date(2024, 1, 1)
    end = datetime.date(2025, 1, 1)
    initial_payments = [
        {
            'amount': 100,
            'payment_date': start,
            'actual_payment_date': start,
        },
        {
            'amount': 150,
            'payment_date': start + datetime.timedelta(days=30),
        },
    ]
    policy = ps.add_policy(
        client=client,
        policy_number='P',
        start_date=start,
        end_date=end,
        payments=initial_payments,
        gateway=fake_drive_gateway,
    )
    assert policy.payments.count() == 2

    extra_payments = [
        {
            'amount': 200,
            'payment_date': start + datetime.timedelta(days=60),
            'actual_payment_date': start + datetime.timedelta(days=65),
        },
    ]
    with pytest.raises(ps.DuplicatePolicyError) as exc:
        ps.add_policy(
            client=client,
            policy_number='P',
            start_date=start,
            end_date=end,
            insurance_company='NewCo',
            payments=extra_payments,
            gateway=fake_drive_gateway,
        )
    existing = exc.value.existing_policy
    ps.update_policy(
        existing, insurance_company='NewCo', gateway=fake_drive_gateway
    )
    for p in extra_payments:
        add_payment(
            policy=existing,
            amount=p['amount'],
            payment_date=p['payment_date'],
            actual_payment_date=p['actual_payment_date'],
        )
    payments = list(existing.payments.order_by(Payment.payment_date))
    assert [p.amount for p in payments] == [100, 150, 200]
    assert [p.actual_payment_date for p in payments] == [
        start,
        None,
        start + datetime.timedelta(days=65),
    ]
    assert existing.insurance_company == 'NewCo'


def test_recreate_after_delete(
    in_memory_db, policy_folder_patches, fake_drive_gateway, monkeypatch
):
    client = Client.create(name='C')
    start = datetime.date(2024, 1, 1)
    end = datetime.date(2025, 1, 1)
    captured = {"create": [], "rename": []}

    def capture_create(*args, **kwargs):
        captured["create"].append(kwargs.get("gateway"))
        return None

    def capture_rename(*args, **kwargs):
        captured["rename"].append(kwargs.get("gateway"))
        return (None, None)

    monkeypatch.setattr(ps, "create_policy_folder", capture_create)
    monkeypatch.setattr("services.folder_utils.rename_policy_folder", capture_rename)

    policy = ps.add_policy(
        client=client,
        policy_number='P',
        start_date=start,
        end_date=end,
        payments=[{'amount': 50, 'payment_date': start}],
        gateway=fake_drive_gateway,
    )
    pid = policy.id
    ps.mark_policy_deleted(pid, gateway=fake_drive_gateway)
    new_policy = ps.add_policy(
        client=client,
        policy_number='P',
        start_date=start,
        end_date=end,
        payments=[{'amount': 60, 'payment_date': start + datetime.timedelta(days=10)}],
        gateway=fake_drive_gateway,
    )
    assert new_policy.policy_number == 'P'
    assert new_policy.id != pid
    assert all(g is fake_drive_gateway for g in captured["create"])
    assert captured["rename"] == [fake_drive_gateway]


def test_create_policy_ignores_deleted_duplicates(
    in_memory_db, policy_folder_patches, fake_drive_gateway
):
    db.execute_sql('DROP INDEX IF EXISTS "policy_policy_number"')
    client = Client.create(name='C')
    start = datetime.date(2024, 1, 1)
    end = datetime.date(2025, 1, 1)
    Policy.create(
        client=client,
        policy_number='P',
        start_date=start,
        end_date=end,
        is_deleted=True,
    )
    policy = ps.add_policy(
        client=client,
        policy_number='P',
        start_date=start,
        end_date=end,
        gateway=fake_drive_gateway,
    )
    assert policy.policy_number == 'P'
    assert policy.is_deleted is False
    assert Policy.select().count() == 2


def test_duplicate_detected_with_normalized_policy_number(
    in_memory_db, policy_folder_patches, fake_drive_gateway
):
    client = Client.create(name='C')
    start = datetime.date(2024, 1, 1)
    end = datetime.date(2025, 1, 1)
    ps.add_policy(
        client=client,
        policy_number='ab123',
        start_date=start,
        end_date=end,
        gateway=fake_drive_gateway,
    )
    with pytest.raises(ps.DuplicatePolicyError) as exc:
        ps.add_policy(
            client=client,
            policy_number='AB 123',
            start_date=start,
            end_date=end,
            gateway=fake_drive_gateway,
        )
    assert exc.value.existing_policy.policy_number == 'AB123'


def test_contractor_dash_clears(
    in_memory_db, policy_folder_patches, fake_drive_gateway
):
    client = Client.create(name='C')
    start = datetime.date(2024, 1, 1)
    end = datetime.date(2025, 1, 1)
    policy = ps.add_policy(
        client=client,
        policy_number='P',
        contractor='Some Co',
        start_date=start,
        end_date=end,
        payments=[{'amount': 100, 'payment_date': start}],
        gateway=fake_drive_gateway,
    )
    ps.update_policy(policy, contractor='—', gateway=fake_drive_gateway)
    policy_db = Policy.get_by_id(policy.id)
    assert policy_db.contractor is None


def test_update_policy_logs_simple_values(
    in_memory_db, policy_folder_patches, caplog, fake_drive_gateway
):
    client1 = Client.create(name='C1')
    client2 = Client.create(name='C2')
    deal1 = Deal.create(client=client1, description='D1', start_date=datetime.date(2024, 1, 1))
    policy = ps.add_policy(
        client=client1,
        deal=deal1,
        policy_number='P1',
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2025, 1, 1),
        gateway=fake_drive_gateway,
    )
    deal2 = Deal.create(client=client2, description='D2', start_date=datetime.date(2024, 1, 1))

    caplog.set_level(logging.INFO)
    ps.update_policy(
        policy,
        client_id=client2.id,
        deal_id=deal2.id,
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2025, 1, 1),
        note='N',
        gateway=fake_drive_gateway,
    )

    record = next(r for r in caplog.records if '✏️ Обновление полиса' in r.msg)
    log_data = record.args[2]
    assert log_data['client'] == 'C2'
    assert log_data['deal'] == deal2.id
    assert log_data['start_date'] == '2024-01-01'
    assert log_data['end_date'] == '2025-01-01'
    assert log_data['note'] == 'N'
    assert all(
        isinstance(v, (str, int, float, bool, type(None))) for v in log_data.values()
    )


@pytest.fixture()
def dummy_openai_client():
    def generate_streaming_chunks():
        def make_chunk(tool_calls):
            delta = SimpleNamespace(tool_calls=tool_calls)
            choice = SimpleNamespace(delta=delta)
            return SimpleNamespace(choices=[choice])

        return [
            make_chunk(None),
            make_chunk([]),
            make_chunk(
                [SimpleNamespace(function=SimpleNamespace(arguments='{"a'))]
            ),
            make_chunk(
                [SimpleNamespace(function=SimpleNamespace(arguments='1"}'))]
            ),
        ]

    def fake_stream(**kwargs):
        return iter(generate_streaming_chunks())

    return SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: fake_stream())
        )
    )


def test_chat_streaming_no_attribute_error(monkeypatch, dummy_openai_client):
    monkeypatch.setattr(openai, "OpenAI", lambda *a, **kw: dummy_openai_client)
    monkeypatch.setattr(
        ai_policy_service, "settings", Settings(openai_api_key="key")
    )

    parts = []

    def progress(role, text):
        parts.append(text)

    messages = []
    result = _chat(messages, progress_cb=progress)

    assert result == '{"a1"}'
    assert parts == ['{"a', '1"}']
