"""Простая конфигурация логирования для приложений CRM."""

import logging
import os
from logging.handlers import RotatingFileHandler
from appdirs import user_log_dir


class PeeweeFilter(logging.Filter):
    """Фильтрует SELECT-запросы peewee."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401 - short doc
        """True, если сообщение не начинается с ``SELECT``."""
        msg = str(record.getMessage())
        return not msg.lstrip().startswith("('SELECT")


def setup_logging() -> None:
    """Настраивает вывод логов в консоль и файл ``crm.log``."""
    logs_dir = os.getenv("LOG_DIR") or user_log_dir("crm_desktop")
    logs_dir = os.path.expanduser(logs_dir)
    os.makedirs(logs_dir, exist_ok=True)

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

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
    file_h.setLevel(level)

    console_h = logging.StreamHandler()
    console_h.setFormatter(fmt)
    console_h.setLevel(level)

    logging.basicConfig(
        level=level,
        handlers=[file_h, console_h],
        force=True,  # перезаписываем базовую конфигурацию
        format="%(asctime)s | %(levelname)-8s | %(name)20s │ %(message)s",
    )

    logging.getLogger().setLevel(level)

    # Скрываем SELECT-запросы от peewee
    peewee_logger = logging.getLogger("peewee")
    peewee_logger.addFilter(PeeweeFilter())
