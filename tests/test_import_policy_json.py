from PySide6.QtWidgets import QDialog


def test_open_import_policy_json_shows_message_once(monkeypatch, dummy_main_window):

    created = []

    class DummyDlg:
        def __init__(self, parent=None):
            created.append(1)

        def exec(self):
            return QDialog.Accepted

    monkeypatch.setattr("ui.main_window.ImportPolicyJsonForm", DummyDlg)

    mw = dummy_main_window()
    messages = []
    monkeypatch.setattr(
        mw.status_bar, "showMessage", lambda msg, timeout=0: messages.append(msg)
    )

    mw.open_import_policy_json()

    assert len(created) == 1
    assert len(messages) == 1
    assert "импорт" in messages[0].lower()


def test_open_import_policy_json_cancel_shows_no_message(monkeypatch, dummy_main_window):

    class DummyDlg:
        def __init__(self, parent=None):
            pass

        def exec(self):
            return QDialog.Rejected

    monkeypatch.setattr("ui.main_window.ImportPolicyJsonForm", DummyDlg)

    mw = dummy_main_window()
    messages = []
    monkeypatch.setattr(
        mw.status_bar, "showMessage", lambda msg, timeout=0: messages.append(msg)
    )

    mw.open_import_policy_json()

    assert messages == []

