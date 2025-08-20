"""Валидаторы и нормализаторы входных данных."""

import ast
import operator as op
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
    """Нормализует строку с числом и поддерживает простые выражения.

    Помимо удаления пробелов/букв и замены запятой на точку теперь можно
    вводить простые математические выражения и проценты, например ``10*10``
    или ``5+5``. Процент записывается как ``10%`` и интерпретируется как
    ``10/100``.
    """

    if value is None:
        return None

    text = str(value)
    text = re.sub(r"\s+", "", text)
    text = text.replace("\u00a0", "")
    text = text.replace(",", ".")
    text = re.sub(r"[a-zA-Zа-яА-Я]+", "", text)
    text = text.rstrip(".")

    if text == "":
        return text

    expr = re.sub(r"(\d+(?:\.\d+)?)%", r"(\1/100)", text)

    try:
        node = ast.parse(expr, mode="eval").body

        allowed = {
            ast.Add: op.add,
            ast.Sub: op.sub,
            ast.Mult: op.mul,
            ast.Div: op.truediv,
        }

        def _eval(n):
            if isinstance(n, ast.Constant):
                return n.value
            if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
                return -_eval(n.operand)
            if isinstance(n, ast.BinOp) and type(n.op) in allowed:
                return allowed[type(n.op)](_eval(n.left), _eval(n.right))
            raise ValueError("Недопустимое выражение")

        result = _eval(node)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return str(result)
    except Exception:
        return text


def normalize_policy_number(text: str) -> str:
    """Убирает пробелы и приводит номер полиса к верхнему регистру."""
    return re.sub(r"\s+", "", text or "").upper()

