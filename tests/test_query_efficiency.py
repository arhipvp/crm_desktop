from datetime import date

import pytest

from database.db import db
from database.models import Client, Deal, DealExecutor, Executor, Policy
from services.deal_service import get_all_deals
from services.policies.policy_service import get_all_policies
from services.clients.client_app_service import client_app_service
from services import executor_service as es


@pytest.mark.usefixtures("db_transaction")
def test_get_all_deals_prefetches_client(monkeypatch):
    client = Client.create(name="Client A")
    Deal.create(client=client, description="Deal", start_date=date.today())

    database = db.obj
    executed: list[str] = []
    original_execute_sql = database.execute_sql

    def spy(sql, params=None, *args, **kwargs):
        executed.append(sql)
        return original_execute_sql(sql, params, *args, **kwargs)

    monkeypatch.setattr(database, "execute_sql", spy)

    deals = list(get_all_deals())
    assert len(deals) == 1
    assert len(executed) == 1
    assert "JOIN" in executed[0].upper()

    executed.clear()
    assert deals[0].client.name == "Client A"
    assert not executed, "Должен использоваться предзагруженный клиент без дополнительных SQL-запросов"


@pytest.mark.usefixtures("db_transaction")
def test_get_all_policies_prefetches_client(monkeypatch):
    client = Client.create(name="Client B")
    deal = Deal.create(client=client, description="Deal", start_date=date.today())
    Policy.create(client=client, deal=deal, policy_number="P-1", start_date=date.today())

    database = db.obj
    executed: list[str] = []
    original_execute_sql = database.execute_sql

    def spy(sql, params=None, *args, **kwargs):
        executed.append(sql)
        return original_execute_sql(sql, params, *args, **kwargs)

    monkeypatch.setattr(database, "execute_sql", spy)

    policies = list(get_all_policies())
    assert len(policies) == 1
    assert len(executed) == 1
    assert "JOIN" in executed[0].upper()

    executed.clear()
    assert policies[0].client.name == "Client B"
    assert not executed, "Должен использоваться предзагруженный клиент без дополнительных SQL-запросов"


@pytest.mark.usefixtures("db_transaction")
def test_get_merge_candidates_prefetches_counts(monkeypatch):
    client_one = Client.create(name="Client One")
    client_two = Client.create(name="Client Two")

    Deal.create(client=client_one, description="Deal A", start_date=date.today())
    Deal.create(client=client_two, description="Deal B", start_date=date.today())

    Policy.create(
        client=client_one,
        deal=None,
        policy_number="POLICY-A",
        start_date=date.today(),
    )
    Policy.create(
        client=client_two,
        deal=None,
        policy_number="POLICY-B",
        start_date=date.today(),
    )

    database = db.obj
    executed: list[str] = []
    original_execute_sql = database.execute_sql

    def spy(sql, params=None, *args, **kwargs):
        executed.append(sql)
        return original_execute_sql(sql, params, *args, **kwargs)

    monkeypatch.setattr(database, "execute_sql", spy)

    dtos = client_app_service.get_merge_candidates([client_one.id, client_two.id])

    assert len(dtos) == 2
    assert {dto.id for dto in dtos} == {client_one.id, client_two.id}
    assert len(executed) == 3

    executed.clear()
    assert {(dto.id, dto.deals_count, dto.policies_count) for dto in dtos} == {
        (client_one.id, 1, 1),
        (client_two.id, 1, 1),
    }
    assert not executed, "Количество сделок/полисов должно быть предзагружено без дополнительных SQL"


@pytest.mark.usefixtures("db_transaction")
def test_get_executor_for_deal_fetches_executor_once(monkeypatch):
    client = Client.create(name="Client Exec")
    deal = Deal.create(client=client, description="Deal", start_date=date.today())
    executor = Executor.create(full_name="Executor", tg_id=123, is_active=True)
    DealExecutor.create(deal=deal, executor=executor, assigned_date=date.today())

    database = db.obj
    executed: list[str] = []
    original_execute_sql = database.execute_sql

    def spy(sql, params=None, *args, **kwargs):
        executed.append(sql)
        return original_execute_sql(sql, params, *args, **kwargs)

    monkeypatch.setattr(database, "execute_sql", spy)

    result = es.get_executor_for_deal(deal.id)

    assert result is not None
    assert result.id == executor.id
    assert len(executed) == 1

    executed.clear()
    assert result.full_name == executor.full_name
    assert (
        not executed
    ), "Исполнитель должен быть предзагружен без дополнительных SQL-запросов"
