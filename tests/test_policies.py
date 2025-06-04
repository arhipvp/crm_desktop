from datetime import date
from services.client_service import add_client
from services.deal_service import add_deal
from services.policy_service import add_policy
from database.models import Policy, Task, Payment, Income

def test_add_policy_creates_everything():
    client = add_client(name="Тестовый клиент")
    deal = add_deal(
        client_id=client.id,
        start_date=date(2025, 1, 1),
        description="ОСАГО для VW"
    )

    policy = add_policy(
        client_id=client.id,
        deal_id=deal.id,
        policy_number="ABC123456",
        insurance_company="Тестовая страховая",
        insurance_type="ОСАГО",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )

    assert policy.id is not None
    assert policy.policy_number == "ABC123456"
    assert policy.client.id == client.id
    assert policy.deal.id == deal.id

    # задача продления
    task = Task.get_or_none(Task.policy == policy)
    assert task is not None
    assert "продлить" in task.title

    # нулевой платёж
    payment = Payment.get_or_none(Payment.policy == policy)
    assert payment is not None
    assert payment.amount == 0

    # нулевой доход

    # нулевой доход
    income = Income.get_or_none(Income.payment == payment)
    assert income is not None
    assert income.amount == 0




