import peewee
from PySide6.QtWidgets import QApplication, QTableView, QMenu
from PySide6.QtCore import QPoint

from ui.base.base_table_view import BaseTableView


def _create_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_copy_menu_item(monkeypatch):
    _create_app()

    db = peewee.SqliteDatabase(":memory:")

    class Row(peewee.Model):
        name = peewee.CharField()

        class Meta:
            database = db

    obj = Row(name="test")
    view = BaseTableView(model_class=Row)
    view.set_model_class_and_items(Row, [obj])

    index = view.table.model().index(0, 0)

    def fake_index_at(self, _):
        return index

    monkeypatch.setattr(QTableView, "indexAt", fake_index_at)

    actions_holder = {}

    def fake_exec(self, *_):
        actions_holder["actions"] = list(self.actions())

    monkeypatch.setattr(QMenu, "exec", fake_exec)

    copied = {}

    import ui.base.base_table_view as btv

    def fake_copy(text, *, parent=None):
        copied["text"] = text

    monkeypatch.setattr(btv, "copy_text_to_clipboard", fake_copy)

    view._on_table_menu(QPoint(0, 0))

    actions = actions_holder["actions"]
    texts = [a.text() for a in actions]
    assert "Копировать значение" in texts

    copy_action = next(a for a in actions if a.text() == "Копировать значение")
    copy_action.trigger()

    assert copied["text"] == "test"
