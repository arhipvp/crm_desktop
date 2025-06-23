import types
from datetime import date
import pytest

from services.client_service import add_client
from services.deal_service import add_deal
from services.executor_service import add_executor, assign_executor
from services.task_service import add_task, queue_task, Task


@pytest.fixture
def anyio_backend():
    return "asyncio"


class DummyBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, reply_markup=None, parse_mode=None):
        self.sent.append(chat_id)
        class Msg:
            def __init__(self, cid):
                self.chat_id = cid
                self.message_id = 1

        return Msg(chat_id)


@pytest.mark.anyio
async def test_send_pending_tasks_sends_task(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TG_BOT_TOKEN", "x")
    from telegram_bot import bot as tg_bot
    client = add_client(name="T")
    deal = add_deal(client_id=client.id, start_date=date.today(), description="D")
    ex = add_executor(full_name="Exec", tg_id=123)
    assign_executor(deal.id, ex.tg_id)
    task = add_task(title="t", due_date=date.today(), deal_id=deal.id)
    queue_task(task.id)

    dummy = DummyBot()
    ctx = types.SimpleNamespace(bot=dummy)

    monkeypatch.setattr(tg_bot, "fmt_task", lambda t: "text")
    monkeypatch.setattr(tg_bot, "kb_task", lambda tid: None)

    await tg_bot.send_pending_tasks(ctx)

    task = Task.get_by_id(task.id)
    assert task.dispatch_state == "sent"
    assert task.tg_chat_id == ex.tg_id
    assert dummy.sent == [ex.tg_id]
