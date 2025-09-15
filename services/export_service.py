import csv
import datetime
import logging
from collections import deque

from peewee import Field, ForeignKeyField
from ui.common.ru_headers import RU_HEADERS


logger = logging.getLogger(__name__)


def _model_path(start, target) -> list[str] | None:
    if start == target:
        return []
    queue = deque([(start, [])])
    visited: set = {start}
    while queue:
        model, path = queue.popleft()
        for f in model._meta.sorted_fields:
            if isinstance(f, ForeignKeyField):
                rel = f.rel_model
                if rel in visited:
                    continue
                new_path = path + [f.name]
                if rel == target:
                    return new_path
                queue.append((rel, new_path))
                visited.add(rel)
    return None


def _split_path(field: Field | str | object, obj=None) -> list[str]:
    if isinstance(field, str):
        return field.split("__")
    if isinstance(field, Field) and obj is not None:
        path = _model_path(obj.__class__, field.model) or []
        return path + [field.name]
    name = getattr(field, "name", str(field))
    return [name]


def _header_from_field(field: Field | str | object) -> str:
    key = _split_path(field)[-1]
    return RU_HEADERS.get(key, key)


def export_objects_to_csv(path, objects, fields, headers=None):
    """Export given ORM objects to CSV file."""
    if headers is None:
        headers = [_header_from_field(f) for f in fields]
    logger.debug("Заголовки CSV: %s", headers)
    logger.debug("Количество объектов для экспорта: %d", len(objects))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(headers)
        for obj in objects:
            row = []
            for f in fields:
                if isinstance(obj, dict):
                    key = _split_path(f)[-1]
                    value = obj.get(key, "")
                else:
                    if isinstance(f, str):
                        rel = obj
                        for step in f.split("__"):
                            rel = getattr(rel, step, None)
                            if rel is None:
                                break
                        value = rel if rel is not None else ""
                    else:
                        rel = obj
                        for step in _split_path(f, obj):
                            rel = getattr(rel, step, None)
                            if rel is None:
                                break
                        value = rel if rel is not None else ""
                if isinstance(value, (datetime.date, datetime.datetime)):
                    value = value.strftime("%d.%m.%Y")
                row.append(value)
            writer.writerow(row)
    return len(objects)
