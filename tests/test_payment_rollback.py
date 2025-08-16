import datetime
import pytest
from peewee import SqliteDatabase

from database.db import db
from database.models import Client, Policy, Payment, Income, Expense
from services import payment_service
import services.income_service as income_service
import services.expense_service as expense_service


@pytest.fixture()
def setup_db():
    test_db = SqliteDatabase(':memory:')
    db.initialize(test_db)
    test_db.create_tables([Client, Policy, Payment, Income, Expense])
    yield
    test_db.drop_tables([Client, Policy, Payment, Income, Expense])
    test_db.close()


@pytest.mark.parametrize("fail", ["income", "expense"])
def test_add_payment_rolls_back_on_related_error(setup_db, monkeypatch, fail):
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
        payment_service.add_payment(policy=policy, amount=100, payment_date=d1)

    assert Payment.select().count() == 0
    assert Income.select().count() == 0
    assert Expense.select().count() == 0
