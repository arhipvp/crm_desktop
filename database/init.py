"""Единое место для инициализации Peewee-Proxy `db`.
Вызывайте :func:`init_from_env` в начале entry-point'а.
"""

from __future__ import annotations

import os
import urllib.parse
from peewee import PostgresqlDatabase, SqliteDatabase

from .db import db  # тот самый Proxy
from .models import (
    Client,
    Deal,
    Policy,
    Payment,
    Income,
    Task,
    Expense,
    Executor,
    DealExecutor,
    DealCalculation,
)

ALL_MODELS = [
    Client,
    Deal,
    Policy,
    Payment,
    Income,
    Task,
    Expense,
    Executor,
    DealExecutor,
    DealCalculation,
]

_DEFAULT_ENV = "DATABASE_URL"


def _postgres_from_url(url: str) -> PostgresqlDatabase:
    parsed = urllib.parse.urlparse(url)
    return PostgresqlDatabase(
        database=parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname,
        port=parsed.port or 5432,
    )


def init_from_env(database_url: str | None = None, env_var: str = _DEFAULT_ENV) -> None:
    """Инициализирует :data:`db` из переданного URL или переменной окружения.

    Поддерживает строки вида:
      • ``postgres://user:pass@host:port/dbname``
      • ``sqlite:///absolute/path.db`` или ``sqlite:///:memory:``
    Повторный вызов безопасен.
    """
    if getattr(db, "obj", None):
        return

    url = database_url or os.getenv(env_var)
    if not url:
        raise RuntimeError(f"{env_var} is not set")

    if url.startswith("sqlite"):
        path = url.replace("sqlite:///", "", 1) or ":memory:"
        database = SqliteDatabase(path, pragmas={"foreign_keys": 1})
    else:
        database = _postgres_from_url(url)

    db.initialize(database)
