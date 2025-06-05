import os
from datetime import date
import webbrowser
import urllib.parse
import pytest

from services.client_service import (
    add_client,
    mark_client_deleted,
    build_client_query,
    format_phone_for_whatsapp,
    open_whatsapp,
)
from services.deal_service import add_deal, get_next_deal, get_prev_deal
from services.folder_utils import sanitize_name, extract_folder_id, create_policy_folder
from services.validators import normalize_phone


def test_normalize_phone_and_whatsapp():
    assert normalize_phone("8 (999) 123-45-67") == "+79991234567"
    assert format_phone_for_whatsapp("8 999 123 45 67") == "+79991234567"
    with pytest.raises(ValueError):
        normalize_phone("123")


def test_open_whatsapp(monkeypatch):
    captured = {}
    monkeypatch.setattr(webbrowser, "open", lambda url: captured.setdefault("url", url))
    open_whatsapp("8 (999) 123-45-67", message="привет")
    encoded = urllib.parse.quote("привет")
    assert captured["url"] == f"https://wa.me/89991234567?text={encoded}"


def test_sanitize_and_extract():
    assert sanitize_name("  My <Invalid>:Name*?  ") == "My _Invalid__Name__"
    assert sanitize_name("name.") == "name"
    link = "https://drive.google.com/drive/folders/abc123/"
    assert extract_folder_id(link) == "abc123"
    assert extract_folder_id("") is None


def test_create_policy_folder(drive_root, monkeypatch):
    monkeypatch.setattr(
        "services.folder_utils.GOOGLE_DRIVE_LOCAL_ROOT", str(drive_root)
    )
    path = create_policy_folder("Клиент", "POL123")
    assert path.startswith(str(drive_root))
    assert os.path.isdir(path)


def test_build_client_query_filters():
    add_client(name="Иван")
    deleted = add_client(name="Джон")
    mark_client_deleted(deleted.id)
    assert [c.name for c in build_client_query()] == ["Иван"]
    all_names = {c.name for c in build_client_query(show_deleted=True)}
    assert all_names == {"Иван", "Джон"}
    assert [
        c.name for c in build_client_query(search_text="Джон", show_deleted=True)
    ] == ["Джон"]


def test_next_prev_deal():
    client = add_client(name="Клиент")
    d1 = add_deal(
        client_id=client.id,
        start_date=date(2025, 1, 1),
        description="A",
        reminder_date=date(2025, 1, 1),
    )
    d2 = add_deal(
        client_id=client.id,
        start_date=date(2025, 1, 2),
        description="B",
        reminder_date=date(2025, 1, 2),
    )
    d3 = add_deal(
        client_id=client.id,
        start_date=date(2025, 1, 3),
        description="C",
        reminder_date=date(2025, 1, 2),
    )
    assert get_prev_deal(d1) is None
    assert get_next_deal(d1) == d2
    assert get_prev_deal(d3) == d2
    assert get_next_deal(d2) == d3
    assert get_next_deal(d3) is None
