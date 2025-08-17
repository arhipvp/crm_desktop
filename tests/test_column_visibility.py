import pytest
from peewee import Model, CharField, IntegerField, SqliteDatabase

from ui.base.base_table_view import BaseTableView
import ui.settings as ui_settings


def _create_view(model_class, items):
    view = BaseTableView(model_class=model_class)
    view.set_model_class_and_items(model_class, items)
    return view


def test_hidden_column_persistence(tmp_path, qtbot, monkeypatch):
    monkeypatch.setattr(ui_settings, "SETTINGS_PATH", tmp_path / "settings.json")
    db = SqliteDatabase(":memory:")

    class Dummy(Model):
        name = CharField()
        age = IntegerField()

        class Meta:
            database = db

    db.create_tables([Dummy])
    items = [Dummy(name="Alice", age=30), Dummy(name="Bob", age=25)]

    view = _create_view(Dummy, items)
    qtbot.addWidget(view)
    qtbot.wait(0)
    view.table.setColumnHidden(0, True)
    view.save_table_settings()
    view.close()

    new_view = _create_view(Dummy, items)
    qtbot.addWidget(new_view)
    qtbot.waitUntil(lambda: new_view.table.isColumnHidden(0))
    new_view.close()
