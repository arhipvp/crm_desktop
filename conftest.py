import os
import signal
import pytest
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TEST_TIMEOUT = int(os.environ.get("PYTEST_TIMEOUT", "60"))


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


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
