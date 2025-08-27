import os
import signal
import sys
from pathlib import Path

import pytest
from peewee import SqliteDatabase

# Force tests to use in-memory SQLite by default to avoid touching any real DB.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# ensure project root is on sys.path when running tests
sys.path.append(str(Path(__file__).resolve().parent))

from database.db import db
from database.models import (
    Client,
    Policy,
    Payment,
    Income,
    Expense,
    Deal,
    Executor,
    DealExecutor,
    Task,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TEST_TIMEOUT = int(os.environ.get("PYTEST_TIMEOUT", "60"))


@pytest.fixture(autouse=True)
def watchdog():
    """Fail a test if it hangs longer than the timeout."""
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def handler(signum, frame):  # pragma: no cover - timeout handler
        pytest.fail("Test timeout exceeded", pytrace=False)

    signal.signal(signal.SIGALRM, handler)
    signal.alarm(_TEST_TIMEOUT)
    try:
        yield
    finally:
        signal.alarm(0)


def pytest_runtest_logstart(nodeid, location):
    print(f"-- START {nodeid}")


def pytest_runtest_logfinish(nodeid, location):
    print(f"-- FINISH {nodeid}")


@pytest.fixture()
def in_memory_db(monkeypatch):
    # If db is not initialized yet, bind it to a fresh in-memory DB.
    # If it is already initialized (e.g., by an early init_from_env reading the
    # default DATABASE_URL we set above), reuse that handle.
    test_db = getattr(db, "obj", None)
    if test_db is None:
        test_db = SqliteDatabase(":memory:")
        db.initialize(test_db)
    else:
        # Safety guard: never run tests against a non in-memory DB.
        from peewee import SqliteDatabase as _Sqlite
        if not (isinstance(test_db, _Sqlite) and getattr(test_db, "database", None) == ":memory:"):
            raise RuntimeError("Refusing to run tests on a non in-memory database")

    test_db.create_tables([Client, Policy, Payment, Income, Expense, Deal, Executor, DealExecutor, Task])
    try:
        yield
    finally:
        test_db.drop_tables([Client, Policy, Payment, Income, Expense, Deal, Executor, DealExecutor, Task])
        try:
            test_db.close()
        except Exception:
            pass
