from datetime import date
from services.client_service import add_client
from services.deal_service import add_deal
from services.policy_service import add_policy, update_policy, DuplicatePolicyError
from database.models import Payment, Income


def test_add_policy_creates_everything():
    client = add_client(name="Тестовый клиент")
    deal = add_deal(
        client_id=client.id, start_date=date(2025, 1, 1), description="ОСАГО для VW"
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

    # нулевой платёж
    payment = Payment.get_or_none(Payment.policy == policy)
    assert payment is not None
    assert payment.amount == 0

    # нулевой доход
    income = Income.get_or_none(Income.payment == payment)
    assert income is not None
    assert income.amount == 0


def test_first_payment_paid():
    client = add_client(name="Клиент")
    policy = add_policy(
        client_id=client.id,
        policy_number="FP123",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        payments=[{"amount": 1000, "payment_date": date(2025, 1, 1)}],
        first_payment_paid=True,
    )

    payment = Payment.get(Payment.policy == policy)
    assert payment.actual_payment_date == payment.payment_date
    income = Income.get(Income.payment == payment)
    assert income.received_date is None


def test_add_policy_duplicate_same_data():
    client = add_client(name="Dup")
    add_policy(
        client_id=client.id,
        policy_number="DUP123",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )

    try:
        add_policy(
            client_id=client.id,
            policy_number="DUP123",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
        )
    except DuplicatePolicyError as e:
        msg = str(e)
        assert "Такой полис уже найден" in msg
        assert "совпадают" in msg
    else:
        assert False, "Expected DuplicatePolicyError"


def test_update_policy_duplicate_fields():
    client = add_client(name="UpdDup")
    p1 = add_policy(
        client_id=client.id,
        policy_number="UD1",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    p2 = add_policy(
        client_id=client.id,
        policy_number="UD2",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )

    try:
        update_policy(p2, policy_number="UD1")
    except DuplicatePolicyError as e:
        msg = str(e)
        assert "Такой полис уже найден" in msg
    else:
        assert False, "Expected DuplicatePolicyError"
