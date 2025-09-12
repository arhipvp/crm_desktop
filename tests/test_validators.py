import pytest
from services.validators import normalize_number, normalize_phone

@pytest.mark.parametrize(
    "value, expected",
    [
        ("12 345,67", "12345.67"),
        (None, None),
        ("123руб.", "123"),
        ("12\u00a0345.", "12345"),
        (100, "100"),
        (10.5, "10.5"),
        ("5+5", "10"),
        ("10*10", "100"),
        ("10*10%", "1"),
        pytest.param("5//2", ValueError),
        pytest.param("abc", ValueError),
    ],
)
def test_normalize_number(value, expected):
    if isinstance(expected, type) and issubclass(expected, Exception):
        with pytest.raises(expected, match="Некорректное выражение"):
            normalize_number(value)
    else:
        assert normalize_number(value) == expected


def test_normalize_phone():
    assert normalize_phone("8 (900) 111-22-33") == "+79001112233"
