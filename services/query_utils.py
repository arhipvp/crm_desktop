"""Utility helpers for building filtered Peewee queries."""

from typing import Iterable, Iterator

from peewee import Field, Model, ModelSelect
from playhouse.shortcuts import Cast


def _apply_contains_filters(
    query: ModelSelect, items: Iterable[tuple[Field, str]]
) -> ModelSelect:
    """Internal helper to apply ``contains`` filters to a query."""
    for field, value in items:
        if not value:
            continue
        query = query.where(Cast(field, "TEXT").contains(value))
    return query


def apply_column_filters(
    query: ModelSelect,
    column_filters: dict[str, str] | None,
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
    items: Iterator[tuple[Field, str]] = (
        (field, value)
        for name, value in column_filters.items()
        if (field := getattr(model, name, None)) is not None and isinstance(field, Field)
    )
    return _apply_contains_filters(query, items)


def apply_field_filters(
    query: ModelSelect, field_filters: dict[Field, str] | None
) -> ModelSelect:
    """Apply ``contains`` filters using explicit Peewee :class:`Field` keys."""
    if not field_filters:
        return query
    return _apply_contains_filters(query, field_filters.items())

