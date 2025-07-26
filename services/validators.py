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
        raise ValueError(
            f"Неверный формат телефона: ожидается 10 цифр, получили {len(digits)}"
        )
    return f"+{digits}"


def normalize_full_name(name: str) -> str:
    """Нормализует ФИО: каждая часть с заглавной буквы.

    Args:
        name: Исходное ФИО.

    Returns:
        str: ФИО в формате ``Иванов Иван Иванович``.
    """
    parts = re.split(r"\s+", name.strip())

    def norm(word: str) -> str:
        return "-".join(p.capitalize() for p in word.split("-") if p)

    return " ".join(norm(p) for p in parts if p)


def normalize_company_name(name: str) -> str:
    """Нормализует название страховой компании с заглавной буквы."""

    parts = re.split(r"\s+", name.strip())

    def norm(word: str) -> str:
        return "-".join(p.capitalize() for p in word.split("-") if p)

    return " ".join(norm(p) for p in parts if p)


def normalize_number(value: str | int | float | None) -> str | None:
    """Нормализует строку с числом, убирая пробелы и меняя запятую на точку."""

    if value is None:
        return None
    text = str(value)
    text = re.sub(r"\s+", "", text)
    text = text.replace("\u00a0", "")
    text = text.replace(",", ".")
    return text

