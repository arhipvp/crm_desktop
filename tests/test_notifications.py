import datetime
from types import SimpleNamespace

import pytest
from database.models import Client, Deal, Task
import services.telegram_service as ts
import services.income_service as ins
import services.task_notifications as tsvc
from services import executor_service as es
from services.policies import policy_service as ps
from services.task_states import SENT


@pytest.mark.parametrize("sent_notify", ["ps"], indirect=True)
def test_notify_on_policy_add(monkeypatch, sent_notify):
    deal = SimpleNamespace(id=42, description='D')
    policy = SimpleNamespace(id=7, policy_number='P', deal_id=deal.id)
    executor = SimpleNamespace(tg_id=101)

    monkeypatch.setattr(es, 'get_executor_for_deal', lambda deal_id: executor)
    monkeypatch.setattr(es, 'is_approved', lambda tg_id: True)
    monkeypatch.setattr(ps, 'get_deal_by_id', lambda deal_id: deal)

    ps._notify_policy_added(policy)

    assert sent_notify.get('tg_id') == executor.tg_id
    assert 'P' in sent_notify.get('text', '')


@pytest.mark.parametrize("sent_notify", ["ts"], indirect=True)
def test_notify_on_unassign(monkeypatch, sent_notify):
    deal = SimpleNamespace(id=77, description='D')
    executor = SimpleNamespace(tg_id=303)

    class DummyDelete:
        def where(self, *_args, **_kwargs):
            return self

        def execute(self):
            return 1

    class DummyDealExecutor:
        deal_id = object()

        @staticmethod
        def delete():
            return DummyDelete()

    class DummyDealModel:
        id = object()

        @staticmethod
        def get_or_none(*_args, **_kwargs):
            return deal

    monkeypatch.setattr(es, 'get_executor_for_deal', lambda deal_id: executor)
    monkeypatch.setattr(es, 'is_approved', lambda tg_id: True)
    monkeypatch.setattr(es, 'DealExecutor', DummyDealExecutor)
    monkeypatch.setattr(es, 'Deal', DummyDealModel)

    es.unassign_executor(deal.id)

    assert sent_notify.get('tg_id') == executor.tg_id
    assert str(deal.id) in sent_notify.get('text', '')


@pytest.mark.parametrize("sent_notify", ["ins"], indirect=True)
def test_notify_on_income_received(monkeypatch, sent_notify):
    deal = SimpleNamespace(id=55, description='D')
    policy = SimpleNamespace(policy_number='P', deal_id=deal.id, deal=deal)
    payment = SimpleNamespace(policy=policy)
    income = SimpleNamespace(amount=10, payment=payment)
    executor = SimpleNamespace(tg_id=404)

    monkeypatch.setattr(es, 'get_executor_for_deal', lambda deal_id: executor)
    monkeypatch.setattr(es, 'is_approved', lambda tg_id: True)

    ins._notify_income_received(income)

    assert sent_notify.get('tg_id') == executor.tg_id
    assert 'P' in sent_notify.get('text', '')


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
