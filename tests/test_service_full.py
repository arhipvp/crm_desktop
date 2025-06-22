from datetime import date
import pytest
import types

from services.client_service import add_client
from services.deal_service import add_deal
from services.policy_service import add_policy
from services.task_service import (
    add_task,
    queue_task,
    pop_next,
    pop_next_by_client,
    get_clients_with_queued_tasks,
    return_to_queue,
    link_telegram,
    mark_done,
    build_task_query,
    get_tasks_page,
    get_pending_tasks,
    unassign_from_telegram,
)
from database.models import Expense


@pytest.fixture(autouse=True)
def extra_tables(test_db):
    if not Expense.table_exists():
        Expense.create_table()
    yield


# ---- Task service ---------------------------------------------------


def test_task_queue_flow():
    client = add_client(name="TClient")
    deal = add_deal(client_id=client.id, start_date=date(2025, 1, 1), description="Q")
    task = add_task(title="qq", due_date=date(2025, 1, 2), deal_id=deal.id)

    queue_task(task.id)
    clients = get_clients_with_queued_tasks()
    assert [c.id for c in clients] == [client.id]

    got = pop_next_by_client(1, client.id)
    assert got.id == task.id
    link_telegram(task.id, 1, 2)
    return_to_queue(task.id)
    got2 = pop_next(1)
    assert got2.id == task.id
    mark_done(task.id)
    unassign_from_telegram(task.id)

    q = build_task_query(deal_id=deal.id)
    assert q.count() >= 1
    page = list(get_tasks_page(1, 10))
    assert task.id in [t.id for t in page]

    assert get_pending_tasks().count() >= 0


class DummyBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, reply_markup=None, parse_mode=None):
        self.sent.append((chat_id, text, reply_markup))


class DummyMessage:
    def __init__(self, bot, text_html="", chat_id=1, reply_to=None):
        self.bot = bot
        self.text_html = text_html
        self.chat_id = chat_id
        self.reply_to_message = reply_to
        self.edits = []
        self.replies = []

    async def edit_text(self, text, parse_mode=None):
        self.edits.append(text)

    async def reply_text(self, text, reply_markup=None):
        self.replies.append((text, reply_markup))


class DummyQuery:
    def __init__(self, data, message, user=None):
        self.data = data
        self.message = message
        self.from_user = user or types.SimpleNamespace(id=0, full_name="Anon", username=None)

    async def answer(self, *a, **k):
        pass


def test_telegram_notify_and_accept(monkeypatch):
    monkeypatch.setenv("TG_BOT_TOKEN", "x")
    monkeypatch.setenv("ADMIN_CHAT_ID", "99")
    import importlib
    tg = importlib.reload(importlib.import_module("telegram_bot.bot"))

    task = add_task(title="t", due_date=date.today())
    task.dispatch_state = "sent"
    task.save()

    bot = DummyBot()
    msg = DummyMessage(bot)
    q = DummyQuery(f"done:{task.id}", msg, user=types.SimpleNamespace(id=5, full_name="Exec", username=None))
    ctx = types.SimpleNamespace(bot=bot)
    import asyncio
    asyncio.run(tg.h_action(types.SimpleNamespace(callback_query=q), ctx))

    assert bot.sent

    admin_msg = DummyMessage(bot)
    q2 = DummyQuery(
        f"accept:{task.id}",
        admin_msg,
        user=types.SimpleNamespace(id=99, full_name="Admin", username=None),
    )
    asyncio.run(tg.h_admin_action(types.SimpleNamespace(callback_query=q2), ctx))

    assert admin_msg.edits
    assert tg.ts.Task.get_by_id(task.id).is_done
    assert any("принята" in m[1] for m in bot.sent if m[0] == msg.chat_id)


def test_telegram_comment_notify(monkeypatch):
    monkeypatch.setenv("TG_BOT_TOKEN", "x")
    monkeypatch.setenv("ADMIN_CHAT_ID", "77")
    import importlib
    tg = importlib.reload(importlib.import_module("telegram_bot.bot"))

    task = add_task(title="t2", due_date=date.today())
    bot = DummyBot()
    reply = DummyMessage(bot, text_html=f"#{task.id}")
    msg = DummyMessage(bot, chat_id=5, reply_to=reply)
    msg.text = "note"
    update = types.SimpleNamespace(
        message=msg,
        effective_user=types.SimpleNamespace(id=5, full_name="Exec", username=None),
    )
    ctx = types.SimpleNamespace(bot=bot)

    import asyncio
    asyncio.run(tg.h_text(update, ctx))

    assert tg.ts.Task.get_by_id(task.id).note
    assert bot.sent


def test_telegram_admin_rework(monkeypatch):
    monkeypatch.setenv("TG_BOT_TOKEN", "x")
    monkeypatch.setenv("ADMIN_CHAT_ID", "55")
    import importlib
    tg = importlib.reload(importlib.import_module("telegram_bot.bot"))

    task = add_task(title="t3", due_date=date.today())
    task.dispatch_state = "sent"
    task.save()

    bot = DummyBot()
    msg = DummyMessage(bot)
    q = DummyQuery(
        f"done:{task.id}",
        msg,
        user=types.SimpleNamespace(id=7, full_name="Exec2", username=None),
    )
    ctx = types.SimpleNamespace(bot=bot)
    import asyncio
    asyncio.run(tg.h_action(types.SimpleNamespace(callback_query=q), ctx))

    admin_msg = DummyMessage(bot)
    q2 = DummyQuery(
        f"rework:{task.id}",
        admin_msg,
        user=types.SimpleNamespace(id=55, full_name="Admin", username=None),
    )
    asyncio.run(tg.h_admin_action(types.SimpleNamespace(callback_query=q2), ctx))

    assert tg.ts.Task.get_by_id(task.id).dispatch_state == "queued"
    assert admin_msg.replies

    reply = DummyMessage(bot, text_html=f"#{task.id}")
    msg2 = DummyMessage(bot, chat_id=55, reply_to=reply)
    msg2.text = "fix"
    asyncio.run(
        tg.h_text(
            types.SimpleNamespace(
                message=msg2,
                effective_user=types.SimpleNamespace(id=55, full_name="Admin", username=None),
            ),
            ctx,
        )
    )

    assert "fix" in tg.ts.Task.get_by_id(task.id).note


def test_telegram_executor_approval(monkeypatch):
    monkeypatch.setenv("TG_BOT_TOKEN", "x")
    monkeypatch.setenv("ADMIN_CHAT_ID", "101")
    import importlib
    tg = importlib.reload(importlib.import_module("telegram_bot.bot"))

    bot = DummyBot()
    msg = DummyMessage(bot)
    q = DummyQuery("get", msg, user=types.SimpleNamespace(id=9, full_name="New Exec", username=None))
    ctx = types.SimpleNamespace(bot=bot)
    import asyncio
    asyncio.run(tg.h_get(types.SimpleNamespace(callback_query=q), ctx))

    assert any("доступ" in m[1].lower() for m in bot.sent)
    assert not tg.es.is_approved(9)

    admin_msg = DummyMessage(bot)
    q2 = DummyQuery("approve_exec:9", admin_msg, user=types.SimpleNamespace(id=101, full_name="Admin", username=None))
    asyncio.run(tg.h_admin_action(types.SimpleNamespace(callback_query=q2), ctx))

    assert tg.es.is_approved(9)
    assert any("одобрены" in m[1] for m in bot.sent if m[0] == msg.chat_id)

