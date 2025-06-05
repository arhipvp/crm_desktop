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
    dlg = TaskDetailView(task)
    qtbot.addWidget(dlg)

    flags = {}
    monkeypatch.setattr(TaskForm, "exec", lambda self: flags.setdefault("edit", True) or True)
    dlg.edit()
    assert flags.get("edit")

    monkeypatch.setattr("ui.views.task_detail_view.confirm", lambda text: True)
    monkeypatch.setattr("ui.views.task_detail_view.mark_task_deleted", lambda tid: flags.setdefault("del", tid))
    monkeypatch.setattr("ui.views.task_detail_view.QMessageBox.information", lambda *a, **k: None)
    dlg.delete()
    assert flags.get("del") == task.id
