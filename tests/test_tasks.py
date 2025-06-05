from datetime import date

from services.client_service import add_client
from services.deal_service import add_deal
from services.task_service import add_task, update_task
from database.models import Task, Deal


def test_complete_task_appends_to_deal():
    client = add_client(name="Клиент")
    deal = add_deal(
        client_id=client.id, start_date=date(2025, 1, 1), description="Тест"
    )
    task = add_task(title="сделать", due_date=date(2025, 1, 2), deal_id=deal.id)

    update_task(task, is_done=True, note="готово")

    task = Task.get_by_id(task.id)
    assert task.is_done
    assert "готово" in (task.note or "")

    deal = Deal.get_by_id(deal.id)
    assert "Задача" in (deal.calculations or "")
