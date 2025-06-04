import re

def normalize_phone(phone: str) -> str:
    """
    Приводит номер к формату +7XXXXXXXXXX.
    Удаляет все нецифровые символы, берёт последние 10 цифр.
    """
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) > 10:
        digits = digits[-10:]
    if len(digits) == 10:
        digits = "7" + digits
    if len(digits) != 11:
        raise ValueError(f"Неверный формат телефона: ожидается 10 цифр, получили {len(digits)}")
    return f"+{digits}"
