from services.deal_service import add_deal, get_deals_by_client_id
from services.client_service import add_client
from database.models import Task


def test_add_deal_creates_deal_and_tasks():
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

    # 4. проверяем задачи
    tasks = Task.select().where(Task.deal == deal)
    task_titles = [t.title for t in tasks]
    assert "расчеты" in task_titles
    assert "собрать документы" in task_titles

    # 5. проверяем, что можно получить через `get_deals_by_client_id`
    deals = get_deals_by_client_id(client.id)
    assert len(deals) == 1
