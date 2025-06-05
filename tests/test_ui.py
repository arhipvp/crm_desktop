import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QMessageBox

from ui.main_window import MainWindow
from ui.views.client_table_view import ClientTableView
from ui.forms.client_form import ClientForm


def test_main_window_tabs(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.tab_widget.count() == 6
    titles = [window.tab_widget.tabText(i) for i in range(6)]
    assert titles == ["Главная", "Клиенты", "Сделки", "Полисы", "Финансы", "Задачи"]


def test_menu_refresh_trigger(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    called = {}

    def refresh():
        called["ok"] = True

    window.menu_bar.register_refresh_callback(refresh)
    window.menu_bar.on_refresh_triggered()
    assert called.get("ok")


def test_menu_show_about(qtbot, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    captured = {}

    def fake_about(parent, title, text):
        captured["title"] = title
        captured["text"] = text

    monkeypatch.setattr(QMessageBox, "about", fake_about)
    window.menu_bar.show_about()
    assert "CRM-десктоп" in captured["text"]


def test_add_new_client_form_called(qtbot, monkeypatch):
    view = ClientTableView()
    qtbot.addWidget(view)
    called = {}

    monkeypatch.setattr(ClientForm, "exec", lambda self: True)
    monkeypatch.setattr(view, "refresh", lambda: called.setdefault("refreshed", True))

    view.add_new()
    assert called.get("refreshed")


def test_task_detail_buttons(qtbot, monkeypatch):
    from datetime import date
    from services.task_service import add_task
    from ui.views.task_detail_view import TaskDetailView
    from ui.forms.task_form import TaskForm

    task = add_task(title="t", due_date=date.today())
    called = {"cb": 0}

    def on_change():
        called["cb"] += 1

    dlg = TaskDetailView(task, on_change=on_change)
    qtbot.addWidget(dlg)

    def fake_exec(self):
        called["edit"] = True
        return True

    monkeypatch.setattr(TaskForm, "exec", fake_exec)
    dlg.edit()
    assert called.get("edit")
    assert called["cb"] == 1

    monkeypatch.setattr("ui.views.task_detail_view.confirm", lambda text: True)
    monkeypatch.setattr("ui.views.task_detail_view.mark_task_deleted", lambda tid: called.setdefault("del", tid))
    monkeypatch.setattr("ui.views.task_detail_view.QMessageBox.information", lambda *a, **k: None)
    dlg.delete()
    assert called.get("del") == task.id
    assert called["cb"] == 2


def test_home_tab_refreshes_on_task_detail_close(qtbot, monkeypatch):
    from datetime import date
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidgetItem
    from services.task_service import add_task
    from ui.views.home_tab import HomeTab

    task = add_task(title="t", due_date=date.today())
    item = QListWidgetItem("t")
    item.setData(Qt.UserRole, task)

    called = {}

    class FakeDialog:
        def __init__(self, *a, **kw):
            pass
        def exec(self):
            called["exec"] = True

    home = HomeTab()
    qtbot.addWidget(home)
    monkeypatch.setattr("ui.views.home_tab.TaskDetailView", FakeDialog)
    monkeypatch.setattr(home, "update_stats", lambda: called.setdefault("upd", True))

    home.open_task_detail(item)
    assert called.get("exec")
    assert called.get("upd")
