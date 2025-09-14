import csv
from codecs import BOM_UTF8
from types import SimpleNamespace

from services.export_service import export_objects_to_csv
from database.models import Client


def test_export_model_and_dict(in_memory_db, tmp_path):
    client = Client.create(name="Alice")
    data = {"name": "Bob", "age": 40}
    fields = [SimpleNamespace(name="name"), SimpleNamespace(name="age")]
    path = tmp_path / "out.csv"

    count = export_objects_to_csv(str(path), [client, data], fields)

    assert count == 2
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    assert lines[0] == "name;age"
    assert lines[1] == "Alice;"
    assert lines[2] == "Bob;40"


def test_export_writes_bom_and_ru_headers(tmp_path):
    fields = [SimpleNamespace(name="payment_date")]
    path = tmp_path / "out.csv"

    export_objects_to_csv(str(path), [], fields)

    raw = path.read_bytes()
    assert raw.startswith(BOM_UTF8)

    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        headers = next(reader)

    assert headers == ["Дата платежа"]
