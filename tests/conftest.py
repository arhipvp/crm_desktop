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
)

TEST_DB = SqliteExtDatabase(":memory:")


@pytest.fixture(autouse=True)
def test_db():
    main_db.initialize(TEST_DB)
    main_db.bind([Client, Deal, Policy, Payment, Income, Task, Expense, Executor, DealExecutor])
    main_db.connect()
    main_db.create_tables([Client, Deal, Policy, Payment, Income, Task, Expense, Executor, DealExecutor])
    yield
    main_db.drop_tables([Client, Deal, Policy, Payment, Income, Task, Expense, Executor, DealExecutor])
    main_db.close()


@pytest.fixture(autouse=True)
def drive_root(tmp_path, monkeypatch):
    """Используем временную папку вместо реального Google Drive."""
    path = tmp_path / "drive"
    monkeypatch.setenv("GOOGLE_DRIVE_LOCAL_ROOT", str(path))
    return path
