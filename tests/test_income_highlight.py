import datetime

import pytest

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
@pytest.mark.parametrize(
    "contractor, expected",
    [
        ("Some Corp", "#ffcccc"),
        (None, None),
    ],
)
def test_income_highlight(contractor, expected):
    income = _make_income(contractor)
    assert get_income_highlight_color(income) == expected

