"""Утилиты форматирования денежных сумм."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

_TWO_PLACES = Decimal("0.01")


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    return Decimal(str(value))


def format_rub(value: Any) -> str:
    """Отформатировать значение в рублях с разделителями тысяч."""

    amount = _to_decimal(value).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    formatted = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    formatted = formatted.replace(" ", "\u202f")
    return f"{formatted} ₽"
