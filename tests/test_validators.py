import pytest
from services.validators import normalize_number, normalize_phone


@pytest.mark.parametrize(
    "value, expected, raises",
    [
        ("12 345,67", "12345.67", None),
        (None, None, None),
        ("123руб.", "123", None),
        ("12\u00a0345.", "12345", None),
        (100, "100", None),
        (10.5, "10.5", None),
        ("5+5", "10", None),
        ("10*10", "100", None),
        ("10*10%", "1", None),
        ("5//2", None, ValueError),
        ("abc", None, ValueError),
    ],
)
def test_normalize_number(value, expected, raises):
    if raises:
        with pytest.raises(raises, match="Некорректное выражение"):
            normalize_number(value)
    else:
        assert normalize_number(value) == expected


def test_normalize_phone():
    assert normalize_phone("8 (900) 111-22-33") == "+79001112233"
