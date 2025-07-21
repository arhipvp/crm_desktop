"""Utility helpers for building filtered Peewee queries."""

from peewee import Field, ModelSelect
from playhouse.shortcuts import Cast


def apply_column_filters(query: ModelSelect, column_filters: dict[str, str] | None, model) -> ModelSelect:
    """Apply simple 'contains' filters for model fields."""
    if not column_filters:
        return query
    for name, value in column_filters.items():
        if not value:
            continue
        field: Field | None = getattr(model, name, None)
        if not field:
            continue
        query = query.where(field.cast("TEXT").contains(value))
    return query


def apply_field_filters(
    query: ModelSelect, field_filters: dict[Field, str] | None
) -> ModelSelect:
    """Apply 'contains' filters using explicit Peewee Field keys."""
    if not field_filters:
        return query
    for field, value in field_filters.items():
        if not value or not isinstance(field, Field):
            continue
        query = query.where(Cast(field, "TEXT").contains(value))
    return query

