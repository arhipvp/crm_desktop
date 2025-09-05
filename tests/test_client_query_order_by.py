import pytest
from database.models import Client
from services.clients.client_service import build_client_query


def test_build_client_query_supports_order_by(in_memory_db):
    Client.create(name="B")
    Client.create(name="A")
    query = build_client_query(order_by="name", order_dir="asc")
    assert [c.name for c in query] == ["A", "B"]
