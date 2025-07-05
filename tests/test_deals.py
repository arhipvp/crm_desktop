from services.deal_service import add_deal, get_deals_by_client_id, update_deal, mark_deal_deleted
from services.client_service import add_client, update_client, mark_client_deleted
from database.models import Task, Deal


def test_add_deal_creates_deal_without_tasks():
    # 1. создаём клиента
    client = add_client(name="Тестовый клиент")

    # 2. создаём сделку
    deal = add_deal(
        client_id=client.id, start_date="2025-01-01", description="ОСАГО для VW"
    )

    # 3. проверяем сделку
    assert deal.id is not None
    assert deal.description == "ОСАГО для VW"
    assert deal.client.id == client.id

    # 4. проверяем отсутствие автоматических задач
    tasks = Task.select().where(Task.deal == deal)
    assert tasks.count() == 0

    # 5. проверяем, что можно получить через `get_deals_by_client_id`
    deals = get_deals_by_client_id(client.id)
    assert len(deals) == 1

def test_add_deal_creates_folder(monkeypatch):
    client = add_client(name="ClientFolder")
    called = {}

    def fake_create_deal_folder(client_name, deal_desc, *, client_drive_link):
        called['args'] = (client_name, deal_desc, client_drive_link)
        return "/tmp/deal_path", "http://link"

    monkeypatch.setattr("services.deal_service.create_deal_folder", fake_create_deal_folder)

    deal = add_deal(
        client_id=client.id,
        start_date="2025-01-01",
        description="My Deal",
    )

    assert called['args'][0] == "Clientfolder"
    assert deal.drive_folder_path == "/tmp/deal_path"
    assert deal.drive_folder_link == "http://link"


def test_update_deal_changes_folder(monkeypatch):
    c1 = add_client(name="C1")
    c2 = add_client(name="C2")
    deal = add_deal(client_id=c1.id, start_date="2025-01-01", description="Old")

    called = {}

    def fake_rename(old_c, old_d, new_c, new_d, link):
        called["args"] = (old_c, old_d, new_c, new_d)
        return f"/tmp/{new_c}_{new_d}", link

    monkeypatch.setattr("services.folder_utils.rename_deal_folder", fake_rename)

    update_deal(deal, client_id=c2.id, description="New")
    deal = get_deals_by_client_id(c2.id)[0]

    assert called["args"] == ("C1", "Old", "C2", "New")
    assert deal.drive_folder_path == "/tmp/C2_New"


def test_mark_deal_deleted_renames_folder(monkeypatch):
    client = add_client(name="DelClient")
    deal = add_deal(client_id=client.id, start_date="2025-01-01", description="D1")

    monkeypatch.setattr(
        "services.folder_utils.rename_deal_folder",
        lambda oc, od, nc, nd, link: (f"/tmp/{nd}", link),
    )

    mark_deal_deleted(deal.id)
    deal = Deal.get_by_id(deal.id)
    assert deal.description.endswith("deleted")
    assert deal.drive_folder_path.endswith("deleted")


def test_update_client_renames_deal_folders(monkeypatch):
    client = add_client(name="Old")
    deal = add_deal(client_id=client.id, start_date="2025-01-01", description="D")

    monkeypatch.setattr(
        "services.client_service.rename_client_folder",
        lambda o, n, l: (f"/tmp/{n}", l),
    )

    called = {}

    def fake_rename(old_c, old_d, new_c, new_d, link):
        called["args"] = (old_c, old_d, new_c, new_d)
        return f"/tmp/{new_c}_{new_d}", link

    monkeypatch.setattr("services.folder_utils.rename_deal_folder", fake_rename)

    update_client(client, name="New")

    deal = Deal.get_by_id(deal.id)
    assert called["args"] == ("Old", "D", "New", "D")
    assert deal.drive_folder_path == "/tmp/New_D"
