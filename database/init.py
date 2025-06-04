"""
Единое место для инициализации Peewee-Proxy `db`.
Вызывайте init_from_env() один раз в самом начале entry-point’а.
"""
from __future__ import annotations

import os
import urllib.parse
from peewee import PostgresqlDatabase, SqliteDatabase
from .db import db  #  <-- тот самый Proxy

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


def init_from_env(env_var: str = _DEFAULT_ENV) -> None:
    """
    Инициализирует `db` из переменной окружения.
    Поддерживает:
      • postgres://user:pass@host:port/dbname
      • sqlite:///absolute/path.db   или  sqlite:///:memory:
    Повторный вызов НЕ ломает приложение.
    """
    if getattr(db, "obj", None):      # Peewee ≥ 3.17 — Proxy уже инициализирован
        return

    url = os.getenv(env_var)
    if not url:
        raise RuntimeError(f"{env_var} is not set")

    if url.startswith("sqlite"):
        # sqlite:///home/me/db.sqlite  → путь начинается после третьего '/'
        path = url.replace("sqlite:///", "", 1) or ":memory:"
        database = SqliteDatabase(path, pragmas={"foreign_keys": 1})
    else:
        database = _postgres_from_url(url)

    db.initialize(database)
