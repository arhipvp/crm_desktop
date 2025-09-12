import datetime
import pytest

from database.models import Client, Policy, Payment, Income, Expense
from services.policies import policy_service as ps


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
