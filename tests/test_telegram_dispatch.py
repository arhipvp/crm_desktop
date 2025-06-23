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


class DummyMessage:
    def __init__(self, cid):
        self.chat_id = cid
        self.sent = []

    async def reply_html(self, text, reply_markup=None):
        self.sent.append((text, reply_markup))
        return types.SimpleNamespace(chat_id=self.chat_id, message_id=len(self.sent))

    async def reply_text(self, text, reply_markup=None):
        self.sent.append((text, reply_markup))
        return types.SimpleNamespace(chat_id=self.chat_id, message_id=len(self.sent))


@pytest.mark.anyio
async def test_show_tasks_sends_each(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TG_BOT_TOKEN", "x")
    from telegram_bot import bot as tg_bot

    client = add_client(name="C")
    deal = add_deal(client_id=client.id, start_date=date.today(), description="D")
    ex = add_executor(full_name="Exec", tg_id=555)
    assign_executor(deal.id, ex.tg_id)
    t1 = add_task(title="a", due_date=date.today(), deal_id=deal.id)
    t2 = add_task(title="b", due_date=date.today(), deal_id=deal.id)

    monkeypatch.setattr(tg_bot, "fmt_task", lambda t: f"task{t.id}")
    monkeypatch.setattr(tg_bot, "kb_task", lambda tid: f"kb{tid}")

    msg = DummyMessage(ex.tg_id)
    user = types.SimpleNamespace(id=ex.tg_id)
    update = types.SimpleNamespace(effective_user=user, message=msg)

    captured = []
    monkeypatch.setattr(tg_bot.ts, "link_telegram", lambda tid, cid, mid: captured.append((tid, cid, mid)))
    monkeypatch.setattr(tg_bot.ts, "get_incomplete_tasks_for_executor", lambda _uid: [t1, t2])

    await tg_bot.h_show_tasks(update, None)

    assert len(msg.sent) == 2
    assert captured == [(t1.id, ex.tg_id, 1), (t2.id, ex.tg_id, 2)]
