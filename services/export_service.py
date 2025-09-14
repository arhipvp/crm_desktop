import csv
import datetime
import logging
from typing import Sequence

from ui.common.ru_headers import RU_HEADERS


logger = logging.getLogger(__name__)


def export_objects_to_csv(path: str, objects: Sequence, fields: Sequence) -> int:
    """Export given ORM objects to CSV file.

    Parameters
    ----------
    path : str
        Destination file path.
    objects : Sequence
        Objects to export.
    fields : Sequence
        List of model fields (peewee Field objects).

    Returns
    -------
    int
        Number of exported rows.
    """
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
                if isinstance(obj, dict):
                    value = obj.get(name, "")
                else:
                    value = getattr(obj, name, "")
                if isinstance(value, (datetime.date, datetime.datetime)):
                    value = value.strftime("%d.%m.%Y")
                row.append(value)
            writer.writerow(row)
    return len(objects)
