"""Простая конфигурация логирования для приложений CRM."""

import logging
import os
from logging.handlers import RotatingFileHandler


class PeeweeFilter(logging.Filter):
    """Фильтрует SELECT-запросы peewee."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401 - short doc
        """True, если сообщение не начинается с ``SELECT``."""
        msg = str(record.getMessage())
        return not msg.lstrip().startswith("('SELECT")


def setup_logging() -> None:
    """Настраивает вывод логов в консоль и файл ``logs/crm.log``."""
    logs_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    os.makedirs(logs_dir, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_h = RotatingFileHandler(
        os.path.join(logs_dir, "crm.log"),
        maxBytes=2_000_000,  # 2 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_h.setFormatter(fmt)

    console_h = logging.StreamHandler()
    console_h.setFormatter(fmt)

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[file_h, console_h],
        force=True,  # перезаписываем базовую конфигурацию
        format="%(asctime)s | %(levelname)-8s | %(name)20s │ %(message)s",
    )

    logging.getLogger().setLevel(logging.DEBUG)

    # Скрываем SELECT-запросы от peewee
    peewee_logger = logging.getLogger("peewee")
    peewee_logger.addFilter(PeeweeFilter())
