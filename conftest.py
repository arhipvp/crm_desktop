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

from services.policies import policy_service as ps
from services import payment_service as pay_svc
import services.telegram_service as ts
import services.income_service as ins

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
def qapp():
    """Ensure a QApplication exists for UI-related tests.

    Creates a minimal offscreen QApplication if none exists and returns it.
    """
    try:
        from PySide6.QtWidgets import QApplication
    except Exception:  # pragma: no cover - optional
        yield None
        return
    app = QApplication.instance() or QApplication([])
    try:
        yield app
    finally:
        try:
            app.quit()
        except Exception:
            pass

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


@pytest.fixture()
def policy_folder_patches(monkeypatch):
    monkeypatch.setattr(ps, "create_policy_folder", lambda *a, **k: None)
    monkeypatch.setattr(ps, "open_folder", lambda *a, **k: None)
    monkeypatch.setattr(
        "services.folder_utils.rename_policy_folder", lambda *a, **k: (None, None)
    )


@pytest.fixture()
def sent_notify(monkeypatch, request):
    sent = {}
    modules = {"ps": ps, "ts": ts, "ins": ins}
    module = modules[request.param]
    monkeypatch.setattr(
        module, "notify_executor", lambda tg_id, text: sent.update(tg_id=tg_id, text=text)
    )
    return sent

@pytest.fixture()
def mock_payments(monkeypatch):
    monkeypatch.setattr(
        pay_svc,
        "add_payment",
        lambda **kw: Payment.create(
            policy=kw["policy"],
            amount=kw["amount"],
            payment_date=kw["payment_date"],
        ),
    )
    monkeypatch.setattr(Payment, "soft_delete", lambda self: self.delete_instance())

@pytest.fixture()
def dummy_main_window(monkeypatch, qapp):
    from PySide6.QtWidgets import QTabWidget, QWidget
    from ui.main_window import MainWindow

    def factory(tab_count: int = 0):
        def dummy_init_tabs(self):
            self.tab_widget = QTabWidget()
            self.setCentralWidget(self.tab_widget)
            for i in range(tab_count):
                self.tab_widget.addTab(QWidget(), str(i))

        monkeypatch.setattr(MainWindow, "init_tabs", dummy_init_tabs)
        monkeypatch.setattr(MainWindow, "on_tab_changed", lambda self, index: None)
        return MainWindow()

    return factory
