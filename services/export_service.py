import csv
import datetime
import logging

from peewee import Field
from ui.common.ru_headers import RU_HEADERS


logger = logging.getLogger(__name__)


def export_objects_to_csv(path, objects, fields, headers=None):
    """Export given ORM objects to CSV file."""
    if headers is None:
        headers = [
            RU_HEADERS.get(getattr(f, "name", str(f)), getattr(f, "name", str(f)))
            for f in fields
        ]
    logger.debug("Заголовки CSV: %s", headers)
    logger.debug("Количество объектов для экспорта: %d", len(objects))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(headers)
        for obj in objects:
            row = []
            for f in fields:
                name = getattr(f, "name", str(f))

                value = ""
                if isinstance(f, Field):
                    rel = obj
                    for step in f.model._meta.name.split("__"):
                        rel = getattr(rel, step, None)
                        if rel is None:
                            break
                    if rel is not None:
                        value = getattr(rel, name, "")
                elif isinstance(obj, dict):
                    value = obj.get(name, "")
                else:
                    value = getattr(obj, name, "")
                if isinstance(value, (datetime.date, datetime.datetime)):
                    value = value.strftime("%d.%m.%Y")
                row.append(value)
            writer.writerow(row)
    return len(objects)
