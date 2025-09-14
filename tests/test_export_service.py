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
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "name;age"
    assert lines[1] == "Alice;"
    assert lines[2] == "Bob;40"
