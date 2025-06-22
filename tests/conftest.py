import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from playhouse.sqlite_ext import SqliteExtDatabase

from database.db import db as main_db
from database.models import (
    Client,
    Deal,
    Income,
    Payment,
    Policy,
    Task,
    Expense,
    Executor,
    DealExecutor,
    DealCalculation,
)
from database.init import init_from_env

TEST_DB = SqliteExtDatabase(":memory:")


@pytest.fixture(autouse=True)
def test_db():
    use_memory = False
    try:
        init_from_env()
        main_db.connect()
    except Exception:
        use_memory = True

    models = [Client, Deal, Policy, Payment, Income, Task, Expense, Executor, DealExecutor, DealCalculation]

    if use_memory:
        main_db.initialize(TEST_DB)
        main_db.connect()

    main_db.bind(models)
    main_db.create_tables(models, safe=True)

    yield

    if use_memory:
        main_db.drop_tables(models)

    if not main_db.is_closed():
        main_db.close()


@pytest.fixture(autouse=True)
def drive_root(tmp_path, monkeypatch):
    """Используем временную папку вместо реального Google Drive."""
    path = tmp_path / "drive"
    monkeypatch.setenv("GOOGLE_DRIVE_LOCAL_ROOT", str(path))
    return path
