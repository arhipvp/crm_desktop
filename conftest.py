import os
import signal
import pytest

try:
    from PySide6 import QtGui  # noqa: F401
except Exception as e:
    pytest.skip(f'PySide6/QtGui unavailable: {e}', allow_module_level=True)

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
