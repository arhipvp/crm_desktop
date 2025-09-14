from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QAbstractItemView, QMessageBox

from database.models import Client
from ui.base.base_table_view import BaseTableView


def test_export_csv_selected_rows(in_memory_db, qapp, tmp_path, monkeypatch):
    c1 = Client.create(name="Alice")
    c2 = Client.create(name="Bob")
    c3 = Client.create(name="Charlie")

    view = BaseTableView(model_class=Client)
    view.set_model_class_and_items(Client, [c1, c2, c3], total_count=3)
    view.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

    sel_model = view.table.selectionModel()
    sel_model.select(
        view.proxy_model.index(0, 0),
        QItemSelectionModel.Select | QItemSelectionModel.Rows,
    )
    sel_model.select(
        view.proxy_model.index(2, 0),
        QItemSelectionModel.Select | QItemSelectionModel.Rows,
    )

    path = tmp_path / "out.csv"
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    view.export_csv(str(path))

    with path.open(encoding="utf-8") as f:
        rows = [line.strip() for line in f if line.strip()]

    assert any("Alice" in row for row in rows[1:])
    assert any("Charlie" in row for row in rows[1:])
    assert all("Bob" not in row for row in rows[1:])


def test_export_csv_no_selection(in_memory_db, qapp, tmp_path, monkeypatch):
    Client.create(name="Alice")
    Client.create(name="Bob")

    view = BaseTableView(model_class=Client)
    view.set_model_class_and_items(Client, list(Client.select()), total_count=2)

    path = tmp_path / "out.csv"
    called = {}

    def fake_warning(*args, **kwargs):
        called["called"] = True

    monkeypatch.setattr(QMessageBox, "warning", fake_warning)
    view.export_csv(str(path))

    assert called.get("called")
    assert not path.exists()
