import datetime
from types import SimpleNamespace

import openai
import pytest

from config import Settings
from database.db import db
from database.models import Client, Policy, Payment
from services.policies import policy_service as ps, ai_policy_service
from services.policies.ai_policy_service import _chat
from services.payment_service import add_payment
def test_policy_merge_additional_payments(in_memory_db, policy_folder_patches):
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
        )
    existing = exc.value.existing_policy
    ps.update_policy(existing, insurance_company='NewCo')
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


def test_recreate_after_delete(in_memory_db, policy_folder_patches):
    client = Client.create(name='C')
    start = datetime.date(2024, 1, 1)
    end = datetime.date(2025, 1, 1)
    policy = ps.add_policy(
        client=client,
        policy_number='P',
        start_date=start,
        end_date=end,
        payments=[{'amount': 50, 'payment_date': start}],
    )
    pid = policy.id
    ps.mark_policy_deleted(pid)
    new_policy = ps.add_policy(
        client=client,
        policy_number='P',
        start_date=start,
        end_date=end,
        payments=[{'amount': 60, 'payment_date': start + datetime.timedelta(days=10)}],
    )
    assert new_policy.policy_number == 'P'
    assert new_policy.id != pid


def test_create_policy_ignores_deleted_duplicates(in_memory_db, policy_folder_patches):
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
    )
    assert policy.policy_number == 'P'
    assert policy.is_deleted is False
    assert Policy.select().count() == 2


def test_duplicate_detected_with_normalized_policy_number(
    in_memory_db, policy_folder_patches
):
    client = Client.create(name='C')
    start = datetime.date(2024, 1, 1)
    end = datetime.date(2025, 1, 1)
    ps.add_policy(
        client=client,
        policy_number='ab123',
        start_date=start,
        end_date=end,
    )
    with pytest.raises(ps.DuplicatePolicyError) as exc:
        ps.add_policy(
            client=client,
            policy_number='AB 123',
            start_date=start,
            end_date=end,
        )
    assert exc.value.existing_policy.policy_number == 'AB123'


def test_contractor_dash_clears(
    in_memory_db, policy_folder_patches
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
    )
    ps.update_policy(policy, contractor='—')
    policy_db = Policy.get_by_id(policy.id)
    assert policy_db.contractor is None


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
