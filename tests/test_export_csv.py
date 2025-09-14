from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QMessageBox,
    QPushButton,
)

from database.models import Client
from ui.base.base_table_view import BaseTableView


def test_export_csv_selected_rows(in_memory_db, qapp, tmp_path, monkeypatch):
    c1 = Client.create(name="Alice")
    c2 = Client.create(name="Bob")
    c3 = Client.create(name="Charlie")

    view = BaseTableView(model_class=Client)
    view.set_model_class_and_items(Client, [c1, c2, c3], total_count=3)
    view.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

    view.table.selectRow(0)
    view.table.selectionModel().select(
        view.proxy_model.index(2, 0),
        QItemSelectionModel.Select | QItemSelectionModel.Rows,
    )
    qapp.processEvents()

    path = tmp_path / "out.csv"
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    view.export_csv(str(path))

    with path.open(encoding="utf-8") as f:
        rows = [line.strip() for line in f if line.strip()]

    assert any("Alice" in row for row in rows[1:])
    assert any("Charlie" in row for row in rows[1:])
    assert all("Bob" not in row for row in rows[1:])


def test_export_button_triggers_csv(in_memory_db, qapp, tmp_path, monkeypatch):
    c1 = Client.create(name="Alice")
    c2 = Client.create(name="Bob")
    c3 = Client.create(name="Charlie")

    called = {"count": 0}
    original = BaseTableView.export_csv

    def spy(self, path: str | None = None):
        called["count"] += 1
        # на всякий случай приводим странные значения к None
        if isinstance(path, bool):
            path = None
        return original(self, path)

    monkeypatch.setattr(BaseTableView, "export_csv", spy)

    view = BaseTableView(model_class=Client)
    view.set_model_class_and_items(Client, [c1, c2, c3], total_count=3)
    view.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

    view.table.selectRow(0)
    view.table.selectionModel().select(
        view.proxy_model.index(2, 0),
        QItemSelectionModel.Select | QItemSelectionModel.Rows,
    )
    qapp.processEvents()

    exported: dict = {}

    def fake_export(path, objs, fields):
        exported["path"] = path
        exported["objs"] = objs

    # подменяем сам экспорт в CSV
    monkeypatch.setattr("ui.base.base_table_view.export_objects_to_csv", fake_export)

    path = tmp_path / "out.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), "csv"))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    # находим кнопку «Экспорт» в FilterControls
    export_btn = next(
        btn
        for btn in view.filter_controls.findChildren(QPushButton)
        if "Экспорт" in btn.text()
    )
    export_btn.click()

    assert called["count"] == 1
    assert exported["path"] == str(path)
    exported_names = [obj.name for obj in exported["objs"]]
    assert "Alice" in exported_names
    assert "Charlie" in exported_names
    assert "Bob" not in exported_names


def test_export_csv_no_selection_warns(in_memory_db, qapp, tmp_path, monkeypatch):
    # Наполнить таблицу, но ничего не выбирать
    Client.create(name="Alice")
    Client.create(name="Bob")

    view = BaseTableView(model_class=Client)
    view.set_model_class_and_items(Client, list(Client.select()), total_count=2)

    path = tmp_path / "out.csv"
    warned = {}

    def fake_warning(*args, **kwargs):
        warned["called"] = True

    monkeypatch.setattr(QMessageBox, "warning", fake_warning)
    view.export_csv(str(path))

    assert warned.get("called")
    assert not path.exists()
