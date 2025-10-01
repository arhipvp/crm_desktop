import pytest

from services import payment_service
from database.models import Payment


@pytest.mark.usefixtures("db_transaction")
def test_update_payment_with_nonexistent_policy_raises_value_error(
    make_policy_with_payment,
):
    _, _, policy, payment = make_policy_with_payment()
    nonexistent_policy_id = policy.id + 1

    with pytest.raises(ValueError, match="Полис с id="):
        payment_service.update_payment(payment, policy_id=nonexistent_policy_id)

    reloaded_payment = Payment.get_by_id(payment.id)
    assert reloaded_payment.policy_id == policy.id
