from datetime import date

from services.client_service import add_client
from services.deal_service import add_deal
from services.task_service import add_task, update_task, mark_done
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


def test_fmt_task_includes_deal_log(monkeypatch):
    monkeypatch.setenv("TG_BOT_TOKEN", "x")
    from telegram_bot.bot import fmt_task

    client = add_client(name="User")
    deal = add_deal(
        client_id=client.id,
        start_date=date(2025, 1, 1),
        description="Desc",
        calculations="note",
    )
    # В некоторых версиях Peewee поле calculations не сохраняется при create
    from database.models import Deal as DealModel
    DealModel.update(calculations="note").where(DealModel.id == deal.id).execute()
    task = add_task(title="t", due_date=date(2025, 1, 2), deal_id=deal.id)

    text = fmt_task(task)
    assert "Журнал" in text
    assert "note" in text


def test_mark_done_updates_deal():
    client = add_client(name="Bot")
    deal = add_deal(
        client_id=client.id,
        start_date=date(2025, 1, 1),
        description="BotDeal",
    )
    task = add_task(title="через бота", due_date=date(2025, 1, 2), deal_id=deal.id)

    mark_done(task.id)

    task = Task.get_by_id(task.id)
    assert task.is_done

    deal = Deal.get_by_id(deal.id)
    assert "Задача" in (deal.calculations or "")


def test_mark_done_logs_task_note():
    client = add_client(name="NoteUser")
    deal = add_deal(
        client_id=client.id,
        start_date=date(2025, 1, 1),
        description="DealWithNotes",
    )
    task = add_task(
        title="check note",
        due_date=date(2025, 1, 2),
        deal_id=deal.id,
    )
    task.note = "комментарий"
    task.save()

    mark_done(task.id)

    deal = Deal.get_by_id(deal.id)
    assert "комментарий" in (deal.calculations or "")
