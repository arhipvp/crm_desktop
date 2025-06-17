from services.deal_service import add_deal, get_deals_by_client_id
from services.client_service import add_client
from database.models import Task


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

    assert called['args'][0] == "ClientFolder"
    assert deal.drive_folder_path == "/tmp/deal_path"
    assert deal.drive_folder_link == "http://link"
