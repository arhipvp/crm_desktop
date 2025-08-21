import pytest
from services.validators import normalize_number, normalize_phone


def test_normalize_number_basic():
    assert normalize_number("12 345,67") == "12345.67"
    assert normalize_number(None) is None
    assert normalize_number("123руб.") == "123"


def test_normalize_number_extra_cases():
    assert normalize_number("12\u00a0345.") == "12345"
    assert normalize_number(100) == "100"
    assert normalize_number(10.5) == "10.5"


def test_normalize_number_math_expressions():
    assert normalize_number("5+5") == "10"
    assert normalize_number("10*10") == "100"
    assert normalize_number("10*10%") == "1"


def test_normalize_number_invalid_expressions():
    with pytest.raises(ValueError, match="Некорректное выражение"):
        normalize_number("5//2")
    with pytest.raises(ValueError, match="Некорректное выражение"):
        normalize_number("abc")


def test_normalize_phone():
    assert normalize_phone("8 (900) 111-22-33") == "+79001112233"
