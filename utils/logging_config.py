"""Простая конфигурация логирования для приложений CRM."""

import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

from config import Settings, get_settings


class PeeweeFilter(logging.Filter):
    """Фильтрует SELECT-запросы peewee."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401 - short doc
        """True, если SQL-запрос не начинается с ``SELECT``."""
        if hasattr(record, "sql"):
            msg = record.sql
        else:
            msg = record.getMessage()
        return not str(msg).lstrip().startswith("SELECT")


def setup_logging(settings: Settings | None = None) -> None:
    """Настраивает вывод логов в консоль и файл ``crm.log``."""
    settings = settings or get_settings()
    logs_dir = Path(settings.log_dir).expanduser()
    logs_dir.mkdir(parents=True, exist_ok=True)

    level_name = settings.log_level
    level = getattr(logging, level_name, logging.INFO)
    if settings.detailed_logging:
        level = logging.DEBUG

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_h = RotatingFileHandler(
        logs_dir / "crm.log",
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
    if not settings.detailed_logging:
        peewee_logger.addFilter(PeeweeFilter())
