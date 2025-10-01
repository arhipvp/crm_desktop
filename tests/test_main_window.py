import base64
import logging
from types import SimpleNamespace

import pytest

import ui.main_window as main_window


def make_stub_tab_widget(count):
    calls = []

    def set_current(index):
        calls.append(index)

    return SimpleNamespace(count=lambda: count, setCurrentIndex=set_current, calls=calls)


def test_apply_main_window_settings_restores_state(monkeypatch):
    geometry = b"geometry-bytes"
    settings = {
        "geometry": base64.b64encode(geometry).decode("ascii"),
        "last_tab": "2",
        "open_maximized": True,
    }
    tab_widget = make_stub_tab_widget(5)
    restored = {}

    def restore_geometry(data):
        restored["value"] = data

    states = []
    monkeypatch.setattr(main_window, "Qt", SimpleNamespace(WindowMaximized=0b10))

    main_window.apply_main_window_settings(
        settings,
        tab_widget,
        restore_geometry,
        lambda: 0b01,
        states.append,
    )

    assert restored["value"] == geometry
    assert tab_widget.calls == [2]
    assert states == [0b01 | 0b10]


def test_apply_main_window_settings_handles_invalid_geometry(monkeypatch, caplog):
    settings = {
        "geometry": base64.b64encode(b"broken").decode("ascii"),
    }
    tab_widget = make_stub_tab_widget(0)

    def raise_error(_data):
        raise ValueError("boom")

    monkeypatch.setattr(main_window, "Qt", SimpleNamespace(WindowMaximized=0b1))

    with caplog.at_level(logging.ERROR):
        main_window.apply_main_window_settings(
            settings,
            tab_widget,
            raise_error,
            lambda: 0,
            lambda _state: None,
        )

    assert "Не удалось восстановить геометрию окна" in caplog.text


def test_apply_main_window_settings_clears_maximized(monkeypatch):
    settings = {"open_maximized": False}
    tab_widget = make_stub_tab_widget(1)
    monkeypatch.setattr(main_window, "Qt", SimpleNamespace(WindowMaximized=0b10))
    states = []

    main_window.apply_main_window_settings(
        settings,
        tab_widget,
        lambda _data: None,
        lambda: 0b11,
        states.append,
    )

    assert states == [0b11 & ~0b10]


@pytest.mark.parametrize(
    "exec_result, expected_messages",
    [
        (1, 1),
        (0, 0),
    ],
)
def test_run_import_policy_dialog(exec_result, expected_messages):
    created = []

    class DummyDialog:
        def exec(self):
            return exec_result

    def factory():
        created.append(True)
        return DummyDialog()

    messages = []
    status_bar = SimpleNamespace(
        showMessage=lambda message, timeout=0: messages.append((message, timeout))
    )

    result = main_window.run_import_policy_dialog(
        factory,
        status_bar,
        accepted_value=1,
    )

    assert created == [True]
    assert result == exec_result
    assert len(messages) == expected_messages
    if messages:
        assert "полис" in messages[0][0].lower()
