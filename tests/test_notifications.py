import datetime
import pytest
from database.models import (
    Client,
    Deal,
    Policy,
    Payment,
    Executor,
    DealExecutor,
    Income,
    Task,
)
from services.policies import policy_service as ps
from services import executor_service as es
import services.telegram_service as ts
import services.income_service as ins
import services.task_notifications as tsvc
from services.task_states import SENT

pytestmark = pytest.mark.slow

def test_notify_on_policy_add(in_memory_db, monkeypatch):
    monkeypatch.setattr(ps, "create_policy_folder", lambda *a, **k: None)
    monkeypatch.setattr(ps, "open_folder", lambda *a, **k: None)

    client = Client.create(name='C')
    deal = Deal.create(client=client, description='D', start_date=datetime.date.today())
    executor = Executor.create(full_name='E', tg_id=1, is_active=True)
    DealExecutor.create(deal=deal, executor=executor, assigned_date=datetime.date.today())

    sent = {}
    monkeypatch.setattr(ps, "notify_executor", lambda tg_id, text: sent.update(tg_id=tg_id, text=text))
    monkeypatch.setattr(ps, "add_payment", lambda **kw: Payment.create(policy=kw['policy'], amount=kw['amount'], payment_date=kw['payment_date']))

    ps.add_policy(
        policy_number='P',
        start_date=datetime.date.today(),
        end_date=datetime.date.today(),
        client=client,
        deal=deal,
        payments=[{"amount": 0, "payment_date": datetime.date.today()}],
    )

    assert sent.get('tg_id') == executor.tg_id
    assert 'P' in sent.get('text', '')


def test_notify_on_unassign(in_memory_db, monkeypatch):
    client = Client.create(name='C')
    deal = Deal.create(client=client, description='D', start_date=datetime.date.today())
    executor = Executor.create(full_name='E', tg_id=1, is_active=True)
    DealExecutor.create(deal=deal, executor=executor, assigned_date=datetime.date.today())

    sent = {}
    monkeypatch.setattr(ts, "notify_executor", lambda tg_id, text: sent.update(tg_id=tg_id, text=text))

    es.unassign_executor(deal.id)

    assert sent.get('tg_id') == executor.tg_id
    assert str(deal.id) in sent.get('text', '')


def test_notify_on_income_received(in_memory_db, monkeypatch):
    client = Client.create(name='C')
    deal = Deal.create(client=client, description='D', start_date=datetime.date.today())
    executor = Executor.create(full_name='E', tg_id=1, is_active=True)
    DealExecutor.create(deal=deal, executor=executor, assigned_date=datetime.date.today())

    policy = Policy.create(
        client=client,
        deal=deal,
        policy_number='P',
        start_date=datetime.date.today(),
        end_date=datetime.date.today(),
    )
    payment = Payment.create(policy=policy, amount=0, payment_date=datetime.date.today())

    sent = {}
    monkeypatch.setattr(ins, "notify_executor", lambda tg_id, text: sent.update(tg_id=tg_id, text=text))

    ins.add_income(payment=payment, amount=10, received_date=datetime.date.today())

    assert sent.get('tg_id') == executor.tg_id
    assert 'P' in sent.get('text', '')


def test_notify_task_resends_message(in_memory_db, monkeypatch):
    client = Client.create(name='C')
    deal = Deal.create(client=client, description='D', start_date=datetime.date.today())
    task = Task.create(
        title='T',
        due_date=datetime.date.today(),
        deal=deal,
        dispatch_state=SENT,
        tg_chat_id=99,
    )

    sent = {}

    def fake_send_exec_task(t, tg_id):
        sent['task_id'] = t.id
        sent['tg_id'] = tg_id

    monkeypatch.setattr(ts, 'send_exec_task', fake_send_exec_task)

    tsvc.notify_task(task.id)

    assert sent == {'task_id': task.id, 'tg_id': 99}
    assert Task.get_by_id(task.id).dispatch_state == SENT
