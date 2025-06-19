import os
import pytest

try:
    import PySide6 # noqa: F401
except Exception as e:  # noqa: BLE001
    pytest.skip(f"PySide6 could not be imported: {e}", allow_module_level=True)
else:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
