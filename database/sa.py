from __future__ import annotations

"""SQLAlchemy engine and session factory for the parallel FastAPI app."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

_DEFAULT_ENV = "DATABASE_URL"


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


engine = None
SessionLocal = None


def init_engine(env_var: str = _DEFAULT_ENV) -> None:
    """Initialize :data:`engine` and :data:`SessionLocal` using ENV var."""
    global engine, SessionLocal
    if engine is not None:
        return
    database_url = os.getenv(env_var)
    if not database_url:
        raise RuntimeError(f"{env_var} is not set")
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
