import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QMessageBox

from ui.main_window import MainWindow
from ui.main_menu import MainMenu
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
        called['ok'] = True

    window.menu_bar.register_refresh_callback(refresh)
    window.menu_bar.on_refresh_triggered()
    assert called.get('ok')


def test_menu_show_about(qtbot, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    captured = {}

    def fake_about(parent, title, text):
        captured['title'] = title
        captured['text'] = text

    monkeypatch.setattr(QMessageBox, 'about', fake_about)
    window.menu_bar.show_about()
    assert 'CRM-десктоп' in captured['text']


def test_add_new_client_form_called(qtbot, monkeypatch):
    view = ClientTableView()
    qtbot.addWidget(view)
    called = {}

    monkeypatch.setattr(ClientForm, 'exec', lambda self: True)
    monkeypatch.setattr(view, 'refresh', lambda: called.setdefault('refreshed', True))

    view.add_new()
    assert called.get('refreshed')
