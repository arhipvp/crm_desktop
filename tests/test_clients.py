from services.client_service import add_client, update_client
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
