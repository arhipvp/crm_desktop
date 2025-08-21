import os
import signal
import sys
from pathlib import Path

import pytest
from peewee import SqliteDatabase

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
    test_db = SqliteDatabase(':memory:')
    db.initialize(test_db)
    test_db.create_tables([Client, Policy, Payment, Income, Expense, Deal, Executor, DealExecutor])
    yield
    test_db.drop_tables([Client, Policy, Payment, Income, Expense, Deal, Executor, DealExecutor])
    test_db.close()
