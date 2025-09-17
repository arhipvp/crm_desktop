import datetime
import pytest

from database.models import Client, Policy, Payment, Income, Expense
from services import expense_service
from services import payment_service as pay_svc
from services.policies import policy_service as policy_svc


def test_sync_policy_payments_adds_and_removes(
    in_memory_db, mock_payments, make_policy_with_payment
):
    d1 = datetime.date(2024, 1, 1)
    d2 = datetime.date(2024, 2, 1)
    d3 = datetime.date(2024, 3, 1)
    client, deal, policy, p1 = make_policy_with_payment(
        client_kwargs={"name": "C"},
        policy_kwargs={"policy_number": "P", "start_date": d1, "end_date": d3},
        payment_kwargs={"amount": 100, "payment_date": d1},
    )
    p2 = Payment.create(policy=policy, amount=200, payment_date=d2)

    pay_svc.sync_policy_payments(
        policy,
        [
            {"amount": 100, "payment_date": d1},  # остаётся
            {"amount": 300, "payment_date": d3},  # новый
        ],
    )

    payments = list(policy.payments)
    assert {(p.payment_date, p.amount) for p in payments} == {
        (d1, 100),
        (d3, 300),
    }
    # Проверяем, что второй платеж удалён
    assert Payment.select().where(Payment.id == p2.id).count() == 0


def test_update_policy_syncs_payments_and_marks_first_paid(
    in_memory_db, mock_payments, policy_folder_patches, make_policy_with_payment
):
    d1 = datetime.date(2024, 1, 1)
    d2 = datetime.date(2024, 2, 1)
    d3 = datetime.date(2024, 3, 1)
    client, deal, policy, _ = make_policy_with_payment(
        client_kwargs={"name": "C"},
        policy_kwargs={"policy_number": "P", "start_date": d1, "end_date": d3},
        payment_kwargs={"amount": 100, "payment_date": d1},
    )
    Payment.create(policy=policy, amount=200, payment_date=d2)

    policy_svc.update_policy(
        policy,
        start_date=d2,
        payments=[
            {"amount": 200, "payment_date": d2},  # остаётся
            {"amount": 300, "payment_date": d3},  # новый
        ],
        first_payment_paid=True,
    )

    payments = list(policy.payments.order_by(Payment.payment_date))
    assert [(p.payment_date, p.amount) for p in payments] == [
        (d2, 200),
        (d3, 300),
    ]
    # Первый платёж (d2) помечен как оплаченный
    assert payments[0].actual_payment_date == payments[0].payment_date
    # Удалённый платёж (d1)
    assert (
        Payment.select()
        .where((Payment.policy == policy) & (Payment.payment_date == d1))
        .count()
        == 0
    )


def test_sync_policy_payments_removes_zero_when_real_exists(
    in_memory_db, mock_payments, make_policy_with_payment
):
    d0 = datetime.date(2024, 1, 1)
    d1 = datetime.date(2024, 2, 1)
    client, deal, policy, zero_payment = make_policy_with_payment(
        client_kwargs={"name": "C"},
        policy_kwargs={"policy_number": "P", "start_date": d0, "end_date": d1},
        payment_kwargs={"amount": 0, "payment_date": d0},
    )

    pay_svc.sync_policy_payments(
        policy,
        [
            {"amount": 0, "payment_date": d0},
            {"amount": 100, "payment_date": d1},
        ],
    )

    payments = list(policy.payments.where(pay_svc.ACTIVE))
    assert {(p.payment_date, p.amount) for p in payments} == {(d1, 100)}
    assert (
        Payment.select()
        .where((Payment.id == zero_payment.id) & (Payment.is_deleted == True))
        .count()
        == 1
    )


def test_sync_policy_payments_marks_zero_relations_deleted(in_memory_db):
    d0 = datetime.date(2024, 1, 1)
    d1 = datetime.date(2024, 2, 1)
    client = Client.create(name="C")
    policy = Policy.create(
        client=client,
        policy_number="P",
        start_date=d0,
        end_date=d1,
        contractor="Контрагент",
    )
    zero_payment = pay_svc.add_payment(
        policy=policy,
        amount=0,
        payment_date=d0,
    )
    zero_income = zero_payment.incomes.get()
    zero_expense = zero_payment.expenses.get()

    pay_svc.sync_policy_payments(
        policy,
        [
            {"amount": 0, "payment_date": d0},
            {"amount": 100, "payment_date": d1},
        ],
    )

    refreshed_payment = Payment.get_by_id(zero_payment.id)
    refreshed_income = Income.get_by_id(zero_income.id)
    refreshed_expense = Expense.get_by_id(zero_expense.id)

    assert refreshed_payment.is_deleted is True
    assert refreshed_income.is_deleted is True
    assert refreshed_expense.is_deleted is True


def test_add_policy_rolls_back_on_payment_error(
    in_memory_db, monkeypatch, policy_folder_patches, mock_payments
):
    client = Client.create(name="C")
    d1 = datetime.date(2024, 1, 1)
    d2 = datetime.date(2024, 2, 1)

    def fail(**kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(policy_svc, "add_payment", fail)

    with pytest.raises(RuntimeError):
        policy_svc.add_policy(
            client=client,
            policy_number="P",
            start_date=d1,
            end_date=d2,
            payments=[{"amount": 100, "payment_date": d1}],
        )

    assert Policy.select().count() == 0
    assert Payment.select().count() == 0


@pytest.mark.parametrize("fail", ["income", "expense"])
def test_add_payment_rolls_back_on_related_error(
    in_memory_db, monkeypatch, mock_payments, fail
):
    import importlib
    import services.income_service as income_service
    import services.expense_service as expense_service

    pay_module = importlib.reload(pay_svc)

    client = Client.create(name="C")
    d1 = datetime.date(2024, 1, 1)
    policy_data = dict(client=client, policy_number="P", start_date=d1, end_date=d1)
    if fail == "expense":
        policy_data["contractor"] = "X"
    policy = Policy.create(**policy_data)

    def boom(**_):
        raise RuntimeError("boom")

    if fail == "income":
        monkeypatch.setattr(income_service, "add_income", boom)
    else:
        monkeypatch.setattr(expense_service, "add_expense", boom)

    with pytest.raises(RuntimeError):
        pay_module.add_payment(policy=policy, amount=100, payment_date=d1)

    assert Payment.select().count() == 0
    assert Income.select().count() == 0
    assert Expense.select().count() == 0


def test_add_policy_rejects_mismatched_first_payment_date(
    in_memory_db, policy_folder_patches
):
    client = Client.create(name="C")
    start_date = datetime.date(2024, 1, 10)
    wrong_payment_date = datetime.date(2024, 1, 5)

    with pytest.raises(
        ValueError,
        match="Дата первого платежа должна совпадать с датой начала полиса.",
    ):
        policy_svc.add_policy(
            client=client,
            policy_number="PX-1",
            start_date=start_date,
            end_date=start_date + datetime.timedelta(days=30),
            payments=[{"amount": 100, "payment_date": wrong_payment_date}],
        )

    assert Policy.select().count() == 0
    assert Payment.select().count() == 0


def test_add_payment_skips_dash_contractor(in_memory_db):
    client = Client.create(name="C")
    d1 = datetime.date(2024, 1, 1)
    policy = Policy.create(
        client=client,
        policy_number="P",
        start_date=d1,
        end_date=d1,
        contractor="—",
    )
    pay_svc.add_payment(policy=policy, amount=100, payment_date=d1)

    assert Payment.select().count() == 1
    assert Income.select().count() == 1
    assert Expense.select().count() == 0


def test_add_contractor_expense_creates_record(in_memory_db):
    d = datetime.date(2024, 1, 1)
    client = Client.create(name="C")
    policy = Policy.create(
        client=client,
        policy_number="P",
        start_date=d,
        end_date=d,
    )
    Payment.create(policy=policy, amount=0, payment_date=d)
    policy.contractor = "X"
    policy.save()
    assert expense_service.get_expense_count_by_policy(policy.id) == 0
    policy_svc.add_contractor_expense(policy)
    assert expense_service.get_expense_count_by_policy(policy.id) == 1
    exp = Expense.get()
    assert exp.expense_type == "контрагент"
    assert exp.amount == 0


def test_add_contractor_expense_requires_contractor(in_memory_db):
    d = datetime.date(2024, 1, 1)
    client = Client.create(name="C")
    policy = Policy.create(
        client=client,
        policy_number="P",
        start_date=d,
        end_date=d,
        contractor="—",
    )
    Payment.create(policy=policy, amount=0, payment_date=d)
    with pytest.raises(ValueError):
        policy_svc.add_contractor_expense(policy)
    assert expense_service.get_expense_count_by_policy(policy.id) == 0


def test_sync_policy_payments_removes_extra_duplicates(
    in_memory_db, mock_payments, make_policy_with_payment
):
    d1 = datetime.date(2024, 1, 1)
    client, deal, policy, p1 = make_policy_with_payment(
        client_kwargs={"name": "C"},
        policy_kwargs={"policy_number": "P", "start_date": d1, "end_date": d1},
        payment_kwargs={"amount": 100, "payment_date": d1},
    )
    p2 = Payment.create(policy=policy, amount=100, payment_date=d1)

    pay_svc.sync_policy_payments(
        policy,
        [
            {"amount": 100, "payment_date": d1},
        ],
    )

    payments = list(policy.payments)
    assert [(p.payment_date, p.amount) for p in payments] == [(d1, 100)]
    assert Payment.select().count() == 1
    remaining_id = payments[0].id
    assert remaining_id in {p1.id, p2.id}


def test_sync_policy_payments_adds_missing_duplicates(
    in_memory_db, mock_payments, make_policy_with_payment
):
    d1 = datetime.date(2024, 1, 1)
    client, deal, policy, p1 = make_policy_with_payment(
        client_kwargs={"name": "C"},
        policy_kwargs={"policy_number": "P", "start_date": d1, "end_date": d1},
        payment_kwargs={"amount": 100, "payment_date": d1},
    )

    pay_svc.sync_policy_payments(
        policy,
        [
            {"amount": 100, "payment_date": d1},
            {"amount": 100, "payment_date": d1},
        ],
    )

    payments = list(policy.payments.order_by(Payment.id))
    assert len(payments) == 2
    assert all((p.payment_date, p.amount) == (d1, 100) for p in payments)
    ids = {p.id for p in payments}
    assert p1.id in ids
    assert len(ids) == 2
