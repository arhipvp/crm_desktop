from services.client_service import (
    add_client,
    update_client,
    mark_client_deleted,
    restore_client,
    mark_clients_deleted,
)
from database.models import Client


def test_add_valid_client():
    client = add_client(
        name="Иван Иванов", phone="8 (999) 123-45-67", email="ivan@test.com"
    )
    assert client.id is not None
    assert client.name == "Иван Иванов"
    assert client.phone == "+79991234567"
    assert client.email == "ivan@test.com"
    assert Client.select().count() == 1


def test_add_client_name_normalization():
    client = add_client(name="иВАНОВ иВАН иВАНОВИЧ")
    assert client.name == "Иванов Иван Иванович"


def test_add_client_without_name_raises():
    try:
        add_client(phone="123")
    except ValueError as e:
        assert "Поле 'name'" in str(e)
    else:
        assert False, "Expected ValueError"


def test_update_client_changes_phone_and_folder(monkeypatch):
    client = add_client(name="Old", phone="8 900 000-00-00")
    monkeypatch.setattr(
        "services.client_service.rename_client_folder",
        lambda o, n, l: (f"/tmp/{n}", f"link/{n}"),
    )
    update_client(client, name="nEW", phone="8 900 111-11-11")
    client = Client.get_by_id(client.id)
    assert client.name == "New"
    assert client.phone == "+79001111111"
    assert client.drive_folder_path.endswith("New")
    assert client.drive_folder_link.endswith("New")


def test_mark_clients_deleted():
    c1 = add_client(name="C1")
    c2 = add_client(name="C2")
    mark_clients_deleted([c1.id, c2.id])
    assert Client.get_by_id(c1.id).is_deleted is True
    assert Client.get_by_id(c2.id).is_deleted is True


def test_mark_client_deleted_renames_folder(monkeypatch):
    c = add_client(name="Cl")
    monkeypatch.setattr(
        "services.folder_utils.rename_client_folder",
        lambda o, n, l: (f"/tmp/{n}", l),
    )
    mark_client_deleted(c.id)
    c = Client.get_by_id(c.id)
    assert c.name.endswith("deleted")
    assert c.drive_folder_path.endswith("deleted")


def test_restore_client():
    c = add_client(name="Del")
    mark_client_deleted(c.id)
    assert Client.get_by_id(c.id).is_deleted
    restore_client(c.id)
    assert not Client.get_by_id(c.id).is_deleted
