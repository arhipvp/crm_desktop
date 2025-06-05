"""Валидаторы и нормализаторы входных данных."""

import re

def normalize_phone(phone: str) -> str:
    """Нормализовать номер телефона.

    Args:
        phone: Исходный номер.

    Returns:
        str: Номер в формате ``+7XXXXXXXXXX``.
    """
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) > 10:
        digits = digits[-10:]
    if len(digits) == 10:
        digits = "7" + digits
    if len(digits) != 11:
        raise ValueError(f"Неверный формат телефона: ожидается 10 цифр, получили {len(digits)}")
    return f"+{digits}"
