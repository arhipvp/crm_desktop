from datetime import date

from services.client_service import add_client
from services.policy_service import add_policy
from services.payment_service import add_payment
from services.income_service import add_income, get_incomes_page
from database.models import Income, Policy


def _create_income(policy_number: str, amount: float, received: date):
    client = add_client(name=policy_number)
    policy = add_policy(
        client_id=client.id,
        policy_number=policy_number,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    payment = add_payment(policy_id=policy.id, amount=amount, payment_date=received)
    return add_income(payment_id=payment.id, amount=amount, received_date=received)


def test_get_incomes_page_sorted_by_amount(test_db):
    _create_income("A", 5, date(2025, 1, 2))
    _create_income("B", 10, date(2025, 1, 3))
    _create_income("C", 1, date(2025, 1, 4))

    items = list(
        get_incomes_page(1, 2, order_by=Income.amount, order_dir="desc")
    )
    assert [i.amount for i in items] == [10, 5]


def test_get_incomes_page_sorted_by_policy_number(test_db):
    i1 = _create_income("B", 5, date(2025, 1, 2))
    i2 = _create_income("A", 10, date(2025, 1, 3))

    items = list(
        get_incomes_page(1, 10, order_by=Policy.policy_number, order_dir="asc")
    )
    nums = [i.payment.policy.policy_number for i in items]
    assert nums == sorted(nums)
