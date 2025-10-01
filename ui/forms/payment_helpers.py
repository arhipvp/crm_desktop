from __future__ import annotations

from datetime import date


def resolve_actual_payment_date(
    payment_date: date | None, stored_actual: date | None, is_checked: bool
) -> date | None:
    """Определить фактическую дату оплаты для сохранения.

    Если чекбокс отмечен, приоритет отдаётся уже сохранённому значению
    фактической даты. Если сохранённого значения нет, используется плановая
    дата платежа. При снятом чекбоксе фактическая дата сбрасывается в ``None``.
    """

    if not is_checked:
        return None

    if stored_actual is not None:
        return stored_actual

    return payment_date

