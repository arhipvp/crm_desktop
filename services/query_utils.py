"""Utility helpers for building filtered Peewee queries."""

from collections.abc import Iterable as IterableABC
from decimal import Decimal
from typing import Any, Iterable, Iterator

from peewee import Field, Model, ModelSelect, Node, fn
from playhouse.shortcuts import Cast

from utils.filter_constants import CHOICE_NULL_TOKEN


def _normalize_filter_values(value: Any) -> tuple[list[str], bool]:
    values: list[str] = []
    includes_null = False

    def _append(text: str) -> None:
        nonlocal includes_null
        if not text:
            return
        if text == CHOICE_NULL_TOKEN:
            includes_null = True
        else:
            values.append(text)

    if value is None:
        return values, includes_null
    if isinstance(value, str):
        _append(value.strip())
        return values, includes_null
    if isinstance(value, IterableABC):
        for item in value:
            if item is None:
                includes_null = True
                continue
            if isinstance(item, str):
                _append(item.strip())
            else:
                _append(str(item).strip())
        return values, includes_null
    _append(str(value).strip())
    return values, includes_null


def _apply_contains_filters(
    query: ModelSelect, items: Iterable[tuple[Field, Any]]
) -> ModelSelect:
    """Internal helper to apply ``contains`` filters to a query."""
    for field, value in items:
        values, include_null = _normalize_filter_values(value)
        if not values and not include_null:
            continue
        condition: Node | None = None
        for candidate in values:
            expr = Cast(field, "TEXT").contains(candidate)
            condition = expr if condition is None else (condition | expr)
        if include_null:
            null_expr = field.is_null(True)
            condition = null_expr if condition is None else (condition | null_expr)
        if condition is not None:
            query = query.where(condition)
    return query


def apply_column_filters(
    query: ModelSelect,
    column_filters: dict[str, Any] | None,
    model: type[Model],
) -> ModelSelect:
    """Apply simple ``contains`` filters for model fields.

    Parameters:
        query: Исходный запрос Peewee.
        column_filters: Словарь «имя поля → значение» для фильтрации.
        model: Класс модели Peewee, из которой берутся поля.
    """
    if not column_filters:
        return query
    items: Iterator[tuple[Field, Any]] = (
        (field, value)
        for name, value in column_filters.items()
        if (field := getattr(model, name, None)) is not None and isinstance(field, Field)
    )
    return _apply_contains_filters(query, items)


def apply_field_filters(
    query: ModelSelect, field_filters: dict[Field, Any] | None
) -> ModelSelect:
    """Apply ``contains`` filters using explicit Peewee :class:`Field` keys."""
    if not field_filters:
        return query
    return _apply_contains_filters(query, field_filters.items())


def build_or_condition(fields: Iterable[Field], value: str) -> Node | None:
    """Сформировать OR-условие ``field.contains(value)`` для разных моделей.

    Parameters:
        fields: Iterable с полями Peewee из разных моделей.
        value: Текст для поиска.

    Returns:
        Peewee-выражение, объединяющее условия ``OR``. ``None`` если список
        полей пуст или значение не задано.
    """
    if not value:
        return None
    condition: Node | None = None
    for field in fields:
        expr = Cast(field, "TEXT").contains(value)
        condition = expr if condition is None else (condition | expr)
    return condition


def apply_search_and_filters(
    query: ModelSelect,
    model: type[Model],
    search_text: str = "",
    column_filters: dict[Field | str, Any] | None = None,
    extra_fields: Iterable[Field] = (),
    extra_condition: Node | None = None,
) -> ModelSelect:
    """Apply substring search and column/field filters to a query.

    Parameters:
        query: Исходный запрос Peewee.
        model: Класс модели для извлечения полей по именам.
        search_text: Текст для поиска по всем полям модели.
        column_filters: Словарь "имя поля или Field → значение".
        extra_fields: Дополнительные поля из других моделей для включения в
            условие ``OR`` поиска.
    """
    combined_condition: Node | None = None

    if search_text:
        fields = [f for f in model._meta.sorted_fields if isinstance(f, Field)]
        if extra_fields:
            fields.extend(extra_fields)
        condition = build_or_condition(fields, search_text)
        if condition is not None:
            combined_condition = condition

    if extra_condition is not None:
        combined_condition = (
            extra_condition
            if combined_condition is None
            else (combined_condition | extra_condition)
        )

    if combined_condition is not None:
        query = query.where(combined_condition)

    field_filters: dict[Field, Any] = {}
    name_filters: dict[str, Any] = {}
    if column_filters:
        for key, val in column_filters.items():
            if isinstance(key, Field):
                field_filters[key] = val
            else:
                name_filters[str(key)] = val

    query = apply_field_filters(query, field_filters)
    query = apply_column_filters(query, name_filters, model)
    return query


def sum_column(query: ModelSelect, field: Field) -> Decimal:
    """Вернуть сумму значений ``field`` для переданного запроса."""

    aggregate = (
        query.clone()
        .limit(None)
        .offset(None)
        .order_by()
        .select(fn.COALESCE(fn.SUM(field), 0))
    )
    value: Any | None = aggregate.scalar()
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))
