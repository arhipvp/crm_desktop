import os
import sys
from datetime import date, datetime, timedelta
import types

import pytest

from services.client_service import add_client
from services.deal_service import add_deal
from services.policy_service import (
    add_policy,
    mark_policy_deleted,
    mark_policy_renewed,
    apply_policy_filters,
)
from services.payment_service import add_payment, apply_payment_filters
from services.expense_service import add_expense, apply_expense_filters
from services.income_service import (
    add_income,
    create_stub_income,
    apply_income_filters,
    build_income_query,
)
from services.dashboard_service import (
    get_basic_stats,
    count_assistant_tasks,
    count_sent_tasks,
    count_working_tasks,
    count_unconfirmed_tasks,
    get_upcoming_tasks,
    get_expiring_policies,
    get_upcoming_deal_reminders,
    get_deal_reminder_counts,
)
from services.folder_utils import (
    rename_client_folder,
    open_local_or_web,
    copy_path_to_clipboard,
    copy_text_to_clipboard,
)
import services.folder_utils as folder_utils
from services.task_service import (
    add_task,
    append_note,
    mark_task_deleted,
    get_incomplete_tasks_for_executor,
    notify_task,
)
from services.executor_service import assign_executor
from utils import screen_utils, time_utils
from database.models import Expense, Income, Payment, Task, Client, Deal, Policy


def test_rename_client_folder_local(tmp_path, monkeypatch):
    root = tmp_path / 'drive'
    old = root / 'Old'
    old.mkdir(parents=True)
    monkeypatch.setenv('GOOGLE_DRIVE_LOCAL_ROOT', str(root))
    monkeypatch.setattr('services.folder_utils.GOOGLE_DRIVE_LOCAL_ROOT', str(root))
    new_path, link = rename_client_folder('Old', 'New', None)
    assert os.path.isdir(new_path)
    assert link is None


def test_open_local_or_web_local(tmp_path, monkeypatch):
    root = tmp_path / 'drive'
    sub = root / 'Foo' / 'Foo'
    sub.mkdir(parents=True)
    monkeypatch.setenv('GOOGLE_DRIVE_LOCAL_ROOT', str(root))
    monkeypatch.setattr('services.folder_utils.GOOGLE_DRIVE_LOCAL_ROOT', str(root))
    captured = {}
    monkeypatch.setattr(os, 'startfile', lambda p: captured.setdefault('path', p), raising=False)
    open_local_or_web('', folder_name='Foo')
    assert captured.get('path') == str(sub)


def test_open_local_or_web_web(monkeypatch):
    monkeypatch.setattr(os.path, 'isdir', lambda p: False)
    captured = {}
    monkeypatch.setattr(sys.modules['webbrowser'], 'open', lambda u: captured.setdefault('url', u))
    open_local_or_web('http://x', folder_name='Foo')
    assert captured.get('url') == 'http://x'


def test_open_local_or_web_prompt(monkeypatch):
    # GUI available but локальная папка отсутствует
    monkeypatch.setattr(os.path, 'isdir', lambda p: False)

    events = {}

    class DummyMB:
        Yes = 1
        Cancel = 2

        @staticmethod
        def question(parent, title, text, buttons):
            events['asked'] = text
            return DummyMB.Cancel

        @staticmethod
        def warning(parent, title, text):
            events['warn'] = text

    class DummyApp:
        @staticmethod
        def instance():
            return True

    monkeypatch.setattr(folder_utils, 'QMessageBox', DummyMB)
    monkeypatch.setattr(folder_utils, 'QApplication', DummyApp)

    captured = {}
    monkeypatch.setattr(sys.modules['webbrowser'], 'open', lambda u: captured.setdefault('url', u))

    open_local_or_web('http://x', folder_name='Foo')

    assert 'asked' in events
    assert captured.get('url') is None


class DummyClipboard:
    def __init__(self):
        self.text = ''
    def setText(self, text):
        self.text = text


class DummyQApp:
    _instance = None
    def __init__(self):
        DummyQApp._instance = self
        self.clip = DummyClipboard()
    @staticmethod
    def instance():
        return DummyQApp._instance
    @staticmethod
    def clipboard():
        return DummyQApp._instance.clip


def test_copy_path_to_clipboard(monkeypatch):
    qmod = types.SimpleNamespace(QGuiApplication=DummyQApp)
    monkeypatch.setitem(sys.modules, 'PySide6.QtGui', qmod)
    DummyQApp()
    msgs = {}
    monkeypatch.setattr('services.folder_utils._msg', lambda t, parent=None: msgs.setdefault('msg', t))
    copy_path_to_clipboard('abc')
    assert DummyQApp._instance.clip.text == 'abc'
    assert msgs['msg']


def test_copy_text_to_clipboard(monkeypatch):
    qmod = types.SimpleNamespace(QGuiApplication=DummyQApp)
    monkeypatch.setitem(sys.modules, 'PySide6.QtGui', qmod)
    DummyQApp()
    msgs = {}
    monkeypatch.setattr('services.folder_utils._msg', lambda t, parent=None: msgs.setdefault('msg', t))
    copy_text_to_clipboard('hello')
    assert DummyQApp._instance.clip.text == 'hello'
    assert msgs['msg']


def test_copy_path_to_clipboard_no_app(monkeypatch):
    class NoApp:
        @staticmethod
        def instance():
            return None
    qmod = types.SimpleNamespace(QGuiApplication=NoApp)
    monkeypatch.setitem(sys.modules, 'PySide6.QtGui', qmod)
    copy_path_to_clipboard('abc')


def test_copy_text_to_clipboard_no_app(monkeypatch):
    class NoApp:
        @staticmethod
        def instance():
            return None

    qmod = types.SimpleNamespace(QGuiApplication=NoApp)
    monkeypatch.setitem(sys.modules, 'PySide6.QtGui', qmod)
    copy_text_to_clipboard('abc')


def test_dashboard_basic_stats_empty():
    assert get_basic_stats() == {'clients': 0, 'deals': 0, 'policies': 0, 'tasks': 0}


def test_dashboard_count_assistant_tasks():
    add_task(title='t1', due_date=date.today(), dispatch_state='sent')
    add_task(title='t2', due_date=date.today())
    assert count_assistant_tasks() == 1


def test_dashboard_count_sent_tasks():
    now = datetime.utcnow()
    add_task(title='a1', due_date=date.today(), queued_at=now)
    add_task(title='a2', due_date=date.today(), queued_at=now, is_done=True)
    assert count_sent_tasks() == 2


def test_dashboard_count_working_tasks():
    add_task(title='w1', due_date=date.today(), tg_chat_id=123)
    add_task(title='w2', due_date=date.today(), tg_chat_id=456, is_done=True)
    assert count_working_tasks() == 2


def test_dashboard_count_unconfirmed_tasks():
    add_task(title='b1', due_date=date.today(), note='done')
    add_task(title='b2', due_date=date.today())
    assert count_unconfirmed_tasks() == 1


def test_dashboard_upcoming_lists_order():
    client = add_client(name='C')
    deal1 = add_deal(client_id=client.id, start_date=date(2025,1,1), description='A', reminder_date=date(2025,1,3))
    deal2 = add_deal(client_id=client.id, start_date=date(2025,1,1), description='B', reminder_date=date(2025,1,1))
    add_policy(
        client_id=client.id,
        deal_id=deal1.id,
        policy_number='1',
        start_date=date(2025,1,1),
        end_date=date(2025,1,10),
        open_folder=lambda *_: None,
    )
    add_policy(
        client_id=client.id,
        deal_id=deal2.id,
        policy_number='2',
        start_date=date(2025,1,1),
        end_date=date(2025,1,5),
        open_folder=lambda *_: None,
    )
    tasks = get_upcoming_tasks()
    # После отказа от автоматического создания задач список может быть пустым
    if len(tasks) >= 2:
        assert tasks[0].due_date <= tasks[1].due_date
    pols = get_expiring_policies()
    assert pols[0].end_date <= pols[1].end_date
    reminders = get_upcoming_deal_reminders()
    assert reminders[0].reminder_date <= reminders[1].reminder_date


def test_get_deal_reminder_counts():
    client = add_client(name='D')
    today = date.today()
    add_deal(client_id=client.id, start_date=today, description='A', reminder_date=today + timedelta(days=1))
    add_deal(client_id=client.id, start_date=today, description='B', reminder_date=today + timedelta(days=1))
    add_deal(client_id=client.id, start_date=today, description='C', reminder_date=today + timedelta(days=2))

    counts = get_deal_reminder_counts()
    # Должны быть данные на все 14 дней, включая нулевые значения
    assert len(counts) == 14
    assert counts[today] == 0
    assert counts[today + timedelta(days=1)] == 2
    assert counts[today + timedelta(days=2)] == 1


def test_apply_expense_filters_include_paid():
    client = add_client(name='E')
    pol = add_policy(client_id=client.id, policy_number='P1', start_date=date(2025,1,1), end_date=date(2025,1,10))
    pay = add_payment(policy_id=pol.id, amount=10, payment_date=date(2025,1,2))
    exp = add_expense(payment_id=pay.id, amount=5, expense_type='agent')
    query = apply_expense_filters(
        Expense.select().join(Payment).join(Policy).join(Client),
        include_paid=False,
    )
    assert list(query) == [exp]
    exp.expense_date = date(2025,1,3)
    exp.save()
    assert list(
        apply_expense_filters(
            Expense.select().join(Payment).join(Policy).join(Client),
            include_paid=False,
        )
    ) == []


def test_apply_income_filters_include_received():
    client = add_client(name='I')
    pol = add_policy(client_id=client.id, policy_number='IP1', start_date=date(2025,1,1), end_date=date(2025,1,10))
    pay = add_payment(policy_id=pol.id, amount=10, payment_date=date(2025,1,2))
    inc1 = add_income(payment_id=pay.id, amount=5, received_date=date(2025,1,3))
    inc2 = add_income(payment_id=pay.id, amount=5)
    q1 = apply_income_filters(Income.select().join(Payment).join(Policy).join(Client), received_date_range=(date(2025,1,2), date(2025,1,4)))
    assert list(q1) == [inc1]
    q2 = apply_income_filters(
        Income.select().join(Payment).join(Policy).join(Client),
        include_received=False,
    )
    res2 = list(q2)
    assert inc2 in res2


def test_income_search_by_deal_description():
    client = add_client(name='S')
    deal = add_deal(client_id=client.id, description='Super deal', start_date=date(2025,1,1))
    pol = add_policy(client_id=client.id, deal_id=deal.id, policy_number='SD1', start_date=date(2025,1,1), end_date=date(2025,1,10))
    pay = add_payment(policy_id=pol.id, amount=10, payment_date=date(2025,1,2))
    inc = add_income(payment_id=pay.id, amount=5)
    q = build_income_query(search_text='Super')
    assert inc in list(q)


def test_apply_payment_filters():
    client = add_client(name='P')
    pol = add_policy(client_id=client.id, policy_number='PP1', start_date=date(2025,1,1), end_date=date(2025,1,10))
    pay1 = add_payment(policy_id=pol.id, amount=10, payment_date=date(2025,1,2), actual_payment_date=date(2025,1,2))
    pay2 = add_payment(policy_id=pol.id, amount=20, payment_date=date(2025,1,3))
    q_unpaid = apply_payment_filters(
        Payment.select().join(Policy).join(Client),
        include_paid=False,
    )
    assert pay2 in list(q_unpaid)
    q_search = apply_payment_filters(
        Payment.select().join(Policy).join(Client),
        search_text='PP1',
        include_paid=True,
    )
    res = list(q_search)
    assert pay1 in res and pay2 in res


def test_screen_utils_no_screen(monkeypatch):
    app = types.SimpleNamespace(primaryScreen=lambda: None)
    monkeypatch.setattr(screen_utils, 'QApplication', app)
    sz = screen_utils.get_scaled_size(800,600)
    assert sz.width() == 800 and sz.height() == 600


def test_time_utils_format():
    s = time_utils.now_str()
    assert len(s) >= 16


def test_create_stub_income_no_payments():
    with pytest.raises(ValueError):
        create_stub_income()


def test_append_and_delete_task():
    task = add_task(title='t', due_date=date.today())
    append_note(task.id, 'x')
    assert 'x' in Task.get_by_id(task.id).note
    mark_task_deleted(task.id)
    assert Task.get_by_id(task.id).is_deleted


def test_notify_task_transitions():
    t1 = add_task(title='n1', due_date=date.today())
    notify_task(t1.id)
    assert Task.get_by_id(t1.id).dispatch_state == 'queued'

    t2 = add_task(title='n2', due_date=date.today(), dispatch_state='sent', tg_chat_id=123)
    notify_task(t2.id)
    res = Task.get_by_id(t2.id)
    assert res.dispatch_state == 'queued' and res.tg_chat_id is None


def test_get_expiring_policies_filters(monkeypatch):
    client = add_client(name='Z')
    p1 = add_policy(
        client_id=client.id,
        policy_number='Z1',
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 10),
        open_folder=lambda *_: None,
    )
    p2 = add_policy(
        client_id=client.id,
        policy_number='Z2',
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 5),
        open_folder=lambda *_: None,
    )
    monkeypatch.setattr(
        "services.folder_utils.rename_policy_folder",
        lambda *a, **k: (f"/tmp/{a[4]}", None),
    )
    mark_policy_deleted(p2.id)
    assert Policy.get_by_id(p2.id).policy_number.endswith("deleted")
    p3 = add_policy(
        client_id=client.id,
        policy_number='Z3',
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 7),
        open_folder=lambda *_: None,
    )
    mark_policy_renewed(p3.id)

    pols = get_expiring_policies()
    assert p1 in pols
    assert p2 not in pols
    assert p3 not in pols


def test_apply_policy_filters_without_deal_only():
    client = add_client(name='POL')
    p1 = add_policy(
        client_id=client.id,
        policy_number='ND1',
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 10),
    )
    deal = add_deal(client_id=client.id, start_date=date(2025, 1, 1), description='D')
    p2 = add_policy(
        client_id=client.id,
        deal_id=deal.id,
        policy_number='D1',
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 10),
    )

    q = apply_policy_filters(Policy.select().join(Client), without_deal_only=True)
    res = list(q)
    assert p1 in res
    assert p2 not in res


def test_get_incomplete_tasks_for_executor_policy():
    client = add_client(name='Exec')
    deal = add_deal(client_id=client.id, start_date=date(2025, 1, 1), description='D')
    policy = add_policy(
        client_id=client.id,
        deal_id=deal.id,
        policy_number='P',
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 10),
    )
    assign_executor(deal_id=deal.id, tg_id=123)
    task = add_task(title='T', due_date=date.today(), policy_id=policy.id)

    tasks = get_incomplete_tasks_for_executor(123)
    assert task in tasks
