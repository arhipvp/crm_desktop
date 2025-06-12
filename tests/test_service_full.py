from datetime import date
import pytest
import types

from services.client_service import (
    add_client,
    get_clients_page,
    mark_client_deleted,
    build_client_query,
    format_phone_for_whatsapp,
    update_client,
)
from services.deal_service import (
    add_deal,
    get_deals_page,
    get_deal_by_id,
    update_deal,
    mark_deal_deleted,
    get_policies_by_deal_id,
    get_tasks_by_deal_id,
)
from services.policy_service import (
    add_policy,
    get_policies_page,
    prolong_policy,
    update_policy,
    get_unique_policy_field_values,
)
from services.payment_service import (
    add_payment,
    get_payments_page,
    update_payment,
    mark_payment_deleted,
)
from services.income_service import (
    add_income,
    get_incomes_page,
    update_income,
    mark_income_deleted,
    create_stub_income,
)
from services.expense_service import (
    add_expense,
    get_expenses_page,
    update_expense,
    mark_expense_deleted,
)
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
from database.models import Expense, Income, Payment, Policy


@pytest.fixture(autouse=True)
def extra_tables(test_db):
    Expense.create_table()
    yield
    Expense.drop_table()


# ---- Client service -------------------------------------------------


def test_client_update_and_query(monkeypatch):
    c1 = add_client(name="A")
    c2 = add_client(name="B")

    monkeypatch.setattr(
        "services.client_service.rename_client_folder",
        lambda o, n, l: (f"/tmp/{n}", f"link/{n}"),
    )
    update_client(c1, phone="8 900 111-22-33")
    assert c1.phone == "+79001112233"

    page = list(get_clients_page(1, 1))
    assert page[0].id == c1.id

    mark_client_deleted(c2.id)
    names = [c.name for c in build_client_query(show_deleted=True)]
    assert set(names) == {"A", "B"}

    assert format_phone_for_whatsapp("8 999 000 00 00") == "+79990000000"


# ---- Deal service ---------------------------------------------------


def test_deal_update_and_pages():
    client = add_client(name="Client")
    deal = add_deal(client_id=client.id, start_date=date(2025, 1, 1), description="D")

    update_deal(deal, calculations="note", is_closed=True, closed_reason="ok")
    assert "Сделка закрыта" in deal.calculations

    page = list(get_deals_page(1, 10, show_closed=True))
    assert page[0].id == deal.id

    policy = add_policy(
        client_id=client.id,
        deal_id=deal.id,
        policy_number="P1",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    task = add_task(title="t", due_date=date(2025, 1, 2), deal_id=deal.id)
    assert policy in list(get_policies_by_deal_id(deal.id))
    tasks = list(get_tasks_by_deal_id(deal.id))
    assert task in tasks

    mark_deal_deleted(deal.id)
    assert get_deal_by_id(deal.id) is None


# ---- Income and Expense service ------------------------------------


def test_income_expense_flow():
    client = add_client(name="IClient")
    policy = add_policy(
        client_id=client.id,
        policy_number="INC1",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    payment = add_payment(
        policy_id=policy.id, amount=100, payment_date=date(2025, 1, 2)
    )

    income = add_income(payment_id=payment.id, amount=50)
    update_income(income, amount=60, received_date=date(2025, 1, 3))
    assert income.amount == 60

    stub = create_stub_income()
    assert isinstance(stub, Income)

    page = list(get_incomes_page(1, 10))
    assert page[0].id == income.id

    mark_income_deleted(income.id)
    assert Income.get_by_id(income.id).is_deleted

    expense = add_expense(payment_id=payment.id, amount=30, expense_type="agent")
    update_expense(expense, amount=40)
    assert expense.amount == 40

    epage = list(get_expenses_page(1, 10))
    assert epage[0].id == expense.id

    mark_expense_deleted(expense.id)
    assert Expense.get_by_id(expense.id).is_deleted


# ---- Payment and Policy service ------------------------------------


def test_payment_policy_flow(monkeypatch):
    client = add_client(name="PClient")
    deal = add_deal(client_id=client.id, start_date=date(2025, 1, 1), description="X")
    policy = add_policy(
        client_id=client.id,
        deal_id=deal.id,
        policy_number="NUM",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    payment = add_payment(policy_id=policy.id, amount=10, payment_date=date(2025, 1, 1))

    update_payment(payment, amount=20)
    assert payment.amount == 20

    page = list(get_payments_page(1, 10))
    ids = [p.id for p in page]
    assert payment.id in ids

    mark_payment_deleted(payment.id)
    assert Payment.get_by_id(payment.id).is_deleted

    update_policy(policy, note="upd")

    def fake_create(**kw):
        obj = Policy(**kw)
        obj.id = 999
        return obj

    monkeypatch.setattr(
        "services.policy_service.Policy.create", staticmethod(fake_create)
    )
    monkeypatch.setattr("services.policy_service.Policy.save", lambda self: None)
    new_policy = prolong_policy(policy)
    assert new_policy.start_date > policy.start_date
    values = get_unique_policy_field_values("insurance_company")
    assert isinstance(values, list)

    ppage = list(get_policies_page(1, 10))
    assert ppage[0].id == policy.id


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
    def __init__(self, data, message):
        self.data = data
        self.message = message

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
    q = DummyQuery(f"done:{task.id}", msg)
    ctx = types.SimpleNamespace(bot=bot)
    import asyncio
    asyncio.run(tg.h_action(types.SimpleNamespace(callback_query=q), ctx))

    assert bot.sent

    admin_msg = DummyMessage(bot)
    q2 = DummyQuery(f"accept:{task.id}", admin_msg)
    asyncio.run(tg.h_admin_action(types.SimpleNamespace(callback_query=q2), ctx))

    assert admin_msg.edits
    assert tg.ts.Task.get_by_id(task.id).is_done


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
    update = types.SimpleNamespace(message=msg)
    ctx = types.SimpleNamespace(bot=bot)

    import asyncio
    asyncio.run(tg.h_text(update, ctx))

    assert tg.ts.Task.get_by_id(task.id).note
    assert bot.sent

