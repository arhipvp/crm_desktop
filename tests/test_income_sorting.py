from datetime import date

from services.client_service import add_client
from services.policy_service import add_policy
from services.payment_service import add_payment
from services.income_service import add_income, get_incomes_page
from services.executor_service import add_executor, assign_executor
from services.deal_service import add_deal
from database.models import Income, Policy, Executor


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


def test_get_incomes_page_sorted_by_executor(test_db):
    client = add_client(name="C")
    add_executor(full_name="AAA", tg_id=1)
    add_executor(full_name="BBB", tg_id=2)
    deal1 = add_deal(client_id=client.id, start_date=date(2025, 1, 1), description="d1")
    assign_executor(deal1.id, 1)
    deal2 = add_deal(client_id=client.id, start_date=date(2025, 1, 2), description="d2")
    assign_executor(deal2.id, 2)
    pol1 = add_policy(client_id=client.id, deal_id=deal1.id, policy_number="P1", start_date=date(2025,1,1), end_date=date(2025,12,31))
    pol2 = add_policy(client_id=client.id, deal_id=deal2.id, policy_number="P2", start_date=date(2025,1,1), end_date=date(2025,12,31))
    pay1 = add_payment(policy_id=pol1.id, amount=5, payment_date=date(2025, 1, 2))
    pay2 = add_payment(policy_id=pol2.id, amount=6, payment_date=date(2025, 1, 3))
    add_income(payment_id=pay1.id, amount=5, received_date=date(2025, 1, 2))
    add_income(payment_id=pay2.id, amount=6, received_date=date(2025, 1, 3))

    items = list(
        get_incomes_page(1, 10, order_by=Executor.full_name, order_dir="desc")
    )
    names = [
        i.payment.policy.deal.executors[0].executor.full_name if i.payment.policy.deal.executors else None
        for i in items
    ]
    assert names == sorted(names, reverse=True)


def test_get_incomes_page_pagination(test_db):
    for i in range(5):
        _create_income(str(i), i + 1, date(2025, 1, i + 1))

    page1 = list(get_incomes_page(1, 2, order_by=Income.id, order_dir="asc"))
    page2 = list(get_incomes_page(2, 2, order_by=Income.id, order_dir="asc"))

    assert len(page1) == 2
    assert len(page2) == 2
    assert page1[0].id != page2[0].id
