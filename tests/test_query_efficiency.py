from datetime import date

import pytest

from database.db import db
from database.models import Client, Deal, Policy
from services.deal_service import get_all_deals
from services.policies.policy_service import get_all_policies


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
