import datetime
import logging
from types import SimpleNamespace

from PySide6.QtCore import QItemSelectionModel, QAbstractTableModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QMessageBox,
    QPushButton,
    QCheckBox,
)

from database.models import Client, Policy
from services.export_service import export_objects_to_csv
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

    def spy(self, path: str | None = None, all_rows: bool = False):
        called["count"] += 1
        if isinstance(path, bool):
            path = None
        return original(self, path, all_rows=all_rows)

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

    def fake_export(path, objs, fields, headers=None):
        exported["path"] = path
        exported["objs"] = objs

    monkeypatch.setattr("ui.base.base_table_view.export_objects_to_csv", fake_export)

    path = tmp_path / "out.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), "csv"))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

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


def test_export_csv_all_rows_option(in_memory_db, qapp, tmp_path, monkeypatch):
    c1 = Client.create(name="Alice")
    c2 = Client.create(name="Bob")
    c3 = Client.create(name="Charlie")

    view = BaseTableView(model_class=Client)
    view.set_model_class_and_items(Client, [c1, c2, c3], total_count=3)
    view.table.selectRow(0)
    qapp.processEvents()

    exported: dict = {}

    def fake_export(path, objs, fields, headers=None):
        exported["objs"] = objs

    monkeypatch.setattr("ui.base.base_table_view.export_objects_to_csv", fake_export)
    path = tmp_path / "all.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), "csv"))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    export_all = next(
        cb for cb in view.filter_controls.findChildren(QCheckBox)
        if "Экспортировать всё" in cb.text()
    )
    export_all.setChecked(True)

    export_btn = next(
        btn for btn in view.filter_controls.findChildren(QPushButton)
        if "Экспорт" in btn.text()
    )
    export_btn.click()

    exported_names = {obj.name for obj in exported["objs"]}
    assert exported_names == {"Alice", "Bob", "Charlie"}


def test_export_csv_no_selection_warns(in_memory_db, qapp, tmp_path, monkeypatch):
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


def test_export_button_calls_export_csv(in_memory_db, qapp, tmp_path, monkeypatch):
    client = Client.create(name="Alice")

    original = BaseTableView.export_csv
    called = {"called": False}

    def spy(self, path: str | None = None, *args, **kwargs):
        called["called"] = True
        return original(self, path, *args, **kwargs)

    monkeypatch.setattr(BaseTableView, "export_csv", spy)

    path = tmp_path / "out.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), "csv"))
    monkeypatch.setattr("ui.base.base_table_view.export_objects_to_csv", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    view = BaseTableView(model_class=Client)
    view.set_model_class_and_items(Client, [client], total_count=1)
    view.table.selectRow(0)
    qapp.processEvents()

    export_btn = next(
        btn
        for btn in view.filter_controls.findChildren(QPushButton)
        if "Экспорт" in btn.text()
    )
    export_btn.click()

    assert called["called"]


def test_export_csv_logs(in_memory_db, qapp, tmp_path, monkeypatch):
    client = Client.create(name="Alice")
    view = BaseTableView(model_class=Client)
    view.set_model_class_and_items(Client, [client], total_count=1)
    view.table.selectRow(0)
    qapp.processEvents()

    path = tmp_path / "out.csv"

    info_msgs: list[str] = []
    debug_msgs: list[str] = []

    def fake_info(self, msg, *args, **kwargs):
        info_msgs.append(msg % args if args else msg)

    def fake_debug(self, msg, *args, **kwargs):
        debug_msgs.append(msg % args if args else msg)

    monkeypatch.setattr(logging.Logger, "info", fake_info)
    monkeypatch.setattr(logging.Logger, "debug", fake_debug)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    view.export_csv(str(path))

    assert any("Запрошен экспорт" in m for m in info_msgs)
    assert any("Экспортировано" in m for m in info_msgs)
    assert any("Сохраняем CSV" in m for m in debug_msgs)
    assert any("Заголовки CSV" in m for m in debug_msgs)
    assert any("Количество объектов" in m for m in debug_msgs)


def test_export_csv_with_dict_model(qapp, tmp_path, monkeypatch):
    data = [{"name": "Alice", "age": 30, "secret": "x"}]

    class DictModel(QAbstractTableModel):
        def __init__(self, objects):
            super().__init__()
            self.objects = objects
            self.fields = [
                SimpleNamespace(name="name"),
                SimpleNamespace(name="age"),
                SimpleNamespace(name="secret"),
            ]

        def rowCount(self, parent=None):
            return len(self.objects)

        def columnCount(self, parent=None):
            return 2

        def data(self, index, role=Qt.DisplayRole):
            if role != Qt.DisplayRole:
                return None
            field = self.fields[index.column()]
            return self.objects[index.row()].get(field.name, "")

        def get_item(self, row):
            return self.objects[row]

    view = BaseTableView(model_class=None)
    view.controller = None
    model = DictModel(data)
    view.model = model
    view.proxy_model.setSourceModel(model)
    view.table.setModel(view.proxy_model)
    view.table.selectRow(0)
    qapp.processEvents()

    path = tmp_path / "dict.csv"
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    view.export_csv(str(path))

    text = path.read_text(encoding="utf-8")
    assert "Alice" in text
    assert "30" in text
    assert "x" not in text


def test_export_csv_custom_headers(qapp, tmp_path, monkeypatch):
    data = [SimpleNamespace(name="Alice", age=30)]

    class HeaderModel(QAbstractTableModel):
        def __init__(self, objects):
            super().__init__()
            self.objects = objects
            self.fields = [
                SimpleNamespace(name="name"),
                SimpleNamespace(name="age"),
            ]

        def rowCount(self, parent=None):
            return len(self.objects)

        def columnCount(self, parent=None):
            return 2

        def data(self, index, role=Qt.DisplayRole):
            if role != Qt.DisplayRole:
                return None
            field = self.fields[index.column()]
            return getattr(self.objects[index.row()], field.name)

        def headerData(self, section, orientation, role=Qt.DisplayRole):
            if orientation == Qt.Horizontal and role == Qt.DisplayRole:
                return ["Имя", "Возраст"][section]
            return None

        def get_item(self, row):
            return self.objects[row]

    view = BaseTableView(model_class=None)
    view.controller = None
    model = HeaderModel(data)
    view.model = model
    view.proxy_model.setSourceModel(model)
    view.table.setModel(view.proxy_model)
    view.table.selectRow(0)
    qapp.processEvents()

    path = tmp_path / "custom.csv"
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    view.export_csv(str(path))

    rows = [
        line.strip()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    assert rows[0] == "Имя;Возраст"


def test_export_csv_related_fields(in_memory_db, tmp_path):
    client = Client.create(name="Alice")
    policy = Policy.create(
        client=client, policy_number="PN123", start_date=datetime.date.today()
    )
    path = tmp_path / "related.csv"
    fields = [Policy.policy_number, Client.name]
    export_objects_to_csv(str(path), [policy], fields)
    text = path.read_text(encoding="utf-8-sig")
    assert "PN123" in text
    assert "Alice" in text


def test_export_csv_with_column_map(qapp, tmp_path, monkeypatch):
    data = [SimpleNamespace(name="Alice", age=30)]

    class EmptyModel(QAbstractTableModel):
        def __init__(self, objects):
            super().__init__()
            self.objects = objects
            self.fields = []

        def rowCount(self, parent=None):
            return len(self.objects)

        def columnCount(self, parent=None):
            return 2

        def data(self, index, role=Qt.DisplayRole):
            if role != Qt.DisplayRole:
                return None
            obj = self.objects[index.row()]
            return obj.name if index.column() == 0 else obj.age

        def get_item(self, row):
            return self.objects[row]

    class MappedView(BaseTableView):
        COLUMN_FIELD_MAP = {
            0: SimpleNamespace(name="name"),
            1: SimpleNamespace(name="age"),
        }

    view = MappedView(model_class=None)
    view.controller = None
    model = EmptyModel(data)
    view.model = model
    view.proxy_model.setSourceModel(model)
    view.table.setModel(view.proxy_model)
    view.table.selectRow(0)
    qapp.processEvents()

    path = tmp_path / "mapped.csv"
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    view.export_csv(str(path))

    text = path.read_text(encoding="utf-8")
    assert "Alice" in text
    assert "30" in text


def test_export_csv_exception_shows_message(in_memory_db, qapp, tmp_path, monkeypatch):
    client = Client.create(name="Alice")
    view = BaseTableView(model_class=Client)
    view.set_model_class_and_items(Client, [client], total_count=1)
    view.table.selectRow(0)
    qapp.processEvents()

    path = tmp_path / "err.csv"

    def fail_export(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("ui.base.base_table_view.export_objects_to_csv", fail_export)

    shown: dict = {}

    def fake_critical(self, title, text):
        shown["title"] = title
        shown["text"] = text

    monkeypatch.setattr(QMessageBox, "critical", fake_critical)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    logged: dict = {}

    def fake_exception(msg, *args, **kwargs):
        logged["msg"] = msg

    monkeypatch.setattr("ui.base.base_table_view.logger.exception", fake_exception)

    view.export_csv(str(path))

    assert shown["title"] == "Экспорт"
    assert shown["text"] == "boom"
    assert logged["msg"] == "Ошибка экспорта CSV"


def test_export_csv_skips_hidden_columns(qapp, tmp_path, monkeypatch):
    data = [SimpleNamespace(name="Alice", age=30)]

    class Model(QAbstractTableModel):
        def __init__(self, objects):
            super().__init__()
            self.objects = objects
            self.fields = [
                SimpleNamespace(name="name"),
                SimpleNamespace(name="age"),
            ]

        def rowCount(self, parent=None):
            return len(self.objects)

        def columnCount(self, parent=None):
            return 2

        def data(self, index, role=Qt.DisplayRole):
            if role != Qt.DisplayRole:
                return None
            field = self.fields[index.column()]
            return getattr(self.objects[index.row()], field.name)

        def headerData(self, section, orientation, role=Qt.DisplayRole):
            if orientation == Qt.Horizontal and role == Qt.DisplayRole:
                return ["Имя", "Возраст"][section]
            return None

        def get_item(self, row):
            return self.objects[row]

    view = BaseTableView(model_class=None)
    view.controller = None
    model = Model(data)
    view.model = model
    view.proxy_model.setSourceModel(model)
    view.table.setModel(view.proxy_model)
    view.table.selectRow(0)
    view.table.setColumnHidden(1, True)
    qapp.processEvents()

    path = tmp_path / "hidden.csv"
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    view.export_csv(str(path))

    rows = [
        line.strip()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    assert rows[0] == "Имя"
    assert rows[1] == "Alice"
