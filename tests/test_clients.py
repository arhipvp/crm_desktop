from services.client_service import add_client
from database.models import Client


def test_add_valid_client():
    print("debug: start test_add_valid_client")
    client = add_client(
        name="Иван Иванов", phone="8 (999) 123-45-67", email="ivan@test.com"
    )
    assert client.id is not None
    assert client.name == "Иван Иванов"
    assert client.phone == "+79991234567"
    assert client.email == "ivan@test.com"
    assert Client.select().count() == 1
    print("debug: end test_add_valid_client")


def test_add_client_without_name_raises():
    print("debug: start test_add_client_without_name_raises")
    try:
        add_client(phone="123")
    except ValueError as e:
        assert "Поле 'name'" in str(e)
    else:
        assert False, "Expected ValueError"
    print("debug: end test_add_client_without_name_raises")
