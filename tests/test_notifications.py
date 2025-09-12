import datetime
import pytest
from database.models import (
    Client,
    Deal,
    Policy,
    Payment,
    Task,
)
from services.policies import policy_service as ps
from services import executor_service as es
import services.telegram_service as ts
import services.income_service as ins
import services.task_notifications as tsvc
from services.task_states import SENT

pytestmark = pytest.mark.slow


TODAY = datetime.date(2024, 1, 1)


@pytest.mark.parametrize("sent_notify", ["ps"], indirect=True)
def test_notify_on_policy_add(
    in_memory_db, mock_payments, policy_folder_patches, sent_notify, make_deal_with_executor
):
    client, deal, executor = make_deal_with_executor()

    ps.add_policy(
        policy_number='P',
        start_date=TODAY,
        end_date=TODAY,
        client=client,
        deal=deal,
        payments=[{"amount": 0, "payment_date": TODAY}],
    )

    assert sent_notify.get('tg_id') == executor.tg_id
    assert 'P' in sent_notify.get('text', '')


@pytest.mark.parametrize("sent_notify", ["ts"], indirect=True)
def test_notify_on_unassign(in_memory_db, sent_notify, make_deal_with_executor):
    client, deal, executor = make_deal_with_executor()

    es.unassign_executor(deal.id)

    assert sent_notify.get('tg_id') == executor.tg_id
    assert str(deal.id) in sent_notify.get('text', '')


@pytest.mark.parametrize("sent_notify", ["ins"], indirect=True)
def test_notify_on_income_received(in_memory_db, sent_notify, make_deal_with_executor):
    client, deal, executor = make_deal_with_executor()

    policy = Policy.create(
        client=client,
        deal=deal,
        policy_number='P',
        start_date=TODAY,
        end_date=TODAY,
    )
    payment = Payment.create(policy=policy, amount=0, payment_date=TODAY)

    ins.add_income(payment=payment, amount=10, received_date=TODAY)

    assert sent_notify.get('tg_id') == executor.tg_id
    assert 'P' in sent_notify.get('text', '')


def test_notify_task_resends_message(in_memory_db, monkeypatch):
    client = Client.create(name='C')
    deal = Deal.create(client=client, description='D', start_date=TODAY)
    task = Task.create(
        title='T',
        due_date=TODAY,
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
