from fastapi.testclient import TestClient

from app.main import app
from app.db import Base, engine, get_session
from sqlalchemy.orm import Session
import pytest


def override_get_session():
    sess = Session(bind=engine)
    try:
        yield sess
    finally:
        sess.close()

app.dependency_overrides[get_session] = override_get_session
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def test_create_and_get_client():
    response = client.post(
        "/api/clients/",
        json={"name": "Alice", "phone": "123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Alice"

    client_id = data["id"]

    get_resp = client.get(f"/api/clients/{client_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Alice"
