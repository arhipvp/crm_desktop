"""Utility helpers for building filtered Peewee queries."""

from peewee import Field, ModelSelect, fn


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
        query = query.where(fn.CAST(field, "TEXT").contains(value))
    return query

