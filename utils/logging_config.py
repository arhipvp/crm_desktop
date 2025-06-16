"""Простая конфигурация логирования для приложений CRM."""

import logging
import os
from logging.handlers import RotatingFileHandler

from config import LOG_FILE, LOGS_DIR


def setup_logging() -> None:
    """Настраивает вывод логов в консоль и файл ``LOG_FILE``."""
    os.makedirs(LOGS_DIR, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_h = RotatingFileHandler(
        LOG_FILE,
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
