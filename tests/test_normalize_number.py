import pytest
from services.validators import normalize_number


def test_normalize_number():
    assert normalize_number("12 345,67") == "12345.67"
    assert normalize_number(" 1 234 ") == "1234"
    assert normalize_number("1\u00a0234,5") == "1234.5"
    assert normalize_number(None) is None
    assert normalize_number(1234) == "1234"
    assert normalize_number("6234.70p") == "6234.70"
    assert normalize_number("123руб.") == "123"
    assert normalize_number("456,78 р.") == "456.78"
