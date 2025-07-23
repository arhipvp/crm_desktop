from services.client_service import add_client
from ui.views.client_table_view import ClientTableView
from PySide6.QtWidgets import QFileDialog, QMessageBox
from services import export_service


def test_export_selected_rows(tmp_path, qtbot, monkeypatch):
    c1 = add_client(name="A")
    view = ClientTableView()
    qtbot.addWidget(view)
    view.load_data()
    view.table.selectRow(0)

    path = tmp_path / "out.csv"
    captured = {}

    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *a, **k: (str(path), "csv"),
    )
    monkeypatch.setattr(
        export_service,
        "export_objects_to_csv",
        lambda p, objs, fields: captured.setdefault("rows", len(objs)),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *a, **k: captured.setdefault("info", True),
    )

    view.export_csv()
    assert captured.get("rows") == 1
    assert captured.get("info")
