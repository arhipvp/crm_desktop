"""Единое место для инициализации Peewee-Proxy `db`.
Вызывайте :func:`init_from_env` в начале entry-point'а.
"""

from __future__ import annotations

import os
import urllib.parse
from peewee import CharField, PostgresqlDatabase, SqliteDatabase
from playhouse.migrate import PostgresqlMigrator, SqliteMigrator, migrate

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


def _get_migrator(database):
    if isinstance(database, PostgresqlDatabase):
        return PostgresqlMigrator(database)
    if isinstance(database, SqliteDatabase):
        return SqliteMigrator(database)
    return None


def _apply_runtime_migrations(database) -> None:
    """Применяет обязательные миграции, которые нужны приложению для старта."""

    migrator = _get_migrator(database)
    if migrator is None:
        return

    with database.connection_context():
        if not database.table_exists("policy"):
            return

        column_names = {column.name for column in database.get_columns("policy")}
        if "drive_folder_path" in column_names:
            return

        with database.atomic():
            migrate(
                migrator.add_column(
                    "policy",
                    "drive_folder_path",
                    CharField(null=True),
                )
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
    _apply_runtime_migrations(database)
