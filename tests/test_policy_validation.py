from datetime import date
import pytest
from services.client_service import add_client
from services.policy_service import add_policy


def test_add_policy_without_number_raises():
    client = add_client(name="NoNumber")
    with pytest.raises(ValueError):
        add_policy(
            client_id=client.id,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
        )
