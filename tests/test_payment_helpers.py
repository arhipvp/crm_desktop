import datetime as dt

import pytest

from ui.forms.payment_helpers import resolve_actual_payment_date


@pytest.mark.parametrize(
    "payment_date, stored_actual, is_checked, expected",
    [
        (
            dt.date(2024, 1, 10),
            dt.date(2024, 1, 15),
            True,
            dt.date(2024, 1, 15),
        ),
        (dt.date(2024, 1, 10), None, True, dt.date(2024, 1, 10)),
        (dt.date(2024, 1, 10), None, False, None),
        (None, dt.date(2024, 1, 15), True, dt.date(2024, 1, 15)),
        (None, None, True, None),
    ],
)
def test_resolve_actual_payment_date(payment_date, stored_actual, is_checked, expected):
    result = resolve_actual_payment_date(payment_date, stored_actual, is_checked)
    assert result == expected
