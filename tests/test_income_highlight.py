import datetime

from database.models import Policy, Payment, Income
from services.income_service import get_income_highlight_color


def _make_income(contractor: str | None) -> Income:
    policy = Policy(
        policy_number="123",
        contractor=contractor,
        start_date=datetime.date.today(),
    )
    payment = Payment(
        policy=policy,
        amount=100,
        payment_date=datetime.date.today(),
    )
    return Income(
        payment=payment,
        amount=10,
        received_date=datetime.date.today(),
    )


def test_highlight_with_contractor():
    income = _make_income("Some Corp")
    assert get_income_highlight_color(income) == "#ffcccc"


def test_no_highlight_without_contractor():
    income = _make_income(None)
    assert get_income_highlight_color(income) is None

