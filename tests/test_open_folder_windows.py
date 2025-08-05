import os
import types
import sys

from services.folder_utils import open_folder

def _make_window(path, focused_flag):
    class DummyWindow:
        def __init__(self, p):
            self.Document = types.SimpleNamespace(
                Folder=types.SimpleNamespace(Self=types.SimpleNamespace(Path=p))
            )
            self.Visible = False
        def Focus(self):
            focused_flag.append(True)
    return DummyWindow(path)

def test_open_folder_reuses_existing_window(monkeypatch):
    focused = []
    shell = types.SimpleNamespace(
        Windows=lambda: [_make_window(r"C:\\path", focused)],
        Open=lambda path: (_ for _ in ()).throw(AssertionError("Open should not be called")),
    )
    monkeypatch.setattr(sys, "platform", "win32")
    stub = types.SimpleNamespace(Dispatch=lambda _: shell)
    monkeypatch.setitem(sys.modules, "win32com", types.SimpleNamespace(client=stub))
    monkeypatch.setitem(sys.modules, "win32com.client", stub)
    monkeypatch.setattr(os.path, "isdir", lambda p: True)
    open_folder(r"C:\\path")
    assert focused, "Existing window should be focused"

def test_open_folder_opens_if_not_found(monkeypatch):
    opened = []
    shell = types.SimpleNamespace(
        Windows=lambda: [],
        Open=lambda path: opened.append(path),
    )
    monkeypatch.setattr(sys, "platform", "win32")
    stub = types.SimpleNamespace(Dispatch=lambda _: shell)
    monkeypatch.setitem(sys.modules, "win32com", types.SimpleNamespace(client=stub))
    monkeypatch.setitem(sys.modules, "win32com.client", stub)
    monkeypatch.setattr(os.path, "isdir", lambda p: True)
    open_folder(r"C:\\another")
    assert opened == [r"C:\\another"]
