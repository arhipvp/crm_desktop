import pytest
from PySide6.QtWidgets import QDialog


@pytest.mark.parametrize(
    "exec_result, expected_messages",
    [
        (QDialog.Accepted, 1),
        (QDialog.Rejected, 0),
    ],
)
def test_open_import_policy_json_message(monkeypatch, dummy_main_window, exec_result, expected_messages):
    created = []

    class DummyDlg:
        def __init__(self, parent=None):
            created.append(1)

        def exec(self):
            return exec_result

    monkeypatch.setattr("ui.main_window.ImportPolicyJsonForm", DummyDlg)

    mw = dummy_main_window()
    messages = []
    monkeypatch.setattr(
        mw.status_bar, "showMessage", lambda msg, timeout=0: messages.append(msg)
    )

    mw.open_import_policy_json()

    assert len(created) == 1
    assert len(messages) == expected_messages
    if expected_messages:
        assert "импорт" in messages[0].lower()

