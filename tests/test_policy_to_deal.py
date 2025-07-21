from datetime import date
from services.client_service import add_client
from services.policy_service import add_policy
from services.deal_service import add_deal_from_policy
from services.policy_service import update_policy
from services.deal_service import add_deal


def test_add_deal_from_policy(monkeypatch):
    client = add_client(name="Client")

    monkeypatch.setattr("services.policy_service.create_policy_folder", lambda *a, **k: "/tmp/policy")
    monkeypatch.setattr("services.policy_service.open_folder", lambda *a, **k: None)
    policy = add_policy(
        client_id=client.id,
        policy_number="P123",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        insurance_type="ОСАГО",
        vehicle_brand="VW",
        vehicle_model="Polo",
    )

    called = {}
    def fake_move(path, cname, deal_desc):
        called['args'] = (path, cname, deal_desc)
        return "/tmp/new"
    monkeypatch.setattr("services.folder_utils.move_policy_folder_to_deal", fake_move)
    monkeypatch.setattr("services.deal_service.create_deal_folder", lambda c, d, *, client_drive_link: ("/tmp/deal", None))

    deal = add_deal_from_policy(policy)

    assert deal.client_id == client.id
    assert policy.deal_id == deal.id
    assert policy.drive_folder_link == "/tmp/new"
    assert called['args'][0] == "/tmp/policy"
    assert deal.description == "ОСАГО VW Polo"
    assert deal.reminder_date == date.today()


def test_update_policy_moves_folder_when_binding(monkeypatch):
    client = add_client(name="Bind")

    monkeypatch.setattr("services.policy_service.create_policy_folder", lambda *a, **k: "/tmp/policy")
    monkeypatch.setattr("services.policy_service.open_folder", lambda *a, **k: None)
    policy = add_policy(
        client_id=client.id,
        policy_number="B1",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )

    deal = add_deal(client_id=client.id, start_date=date(2025, 1, 1), description="D")

    called = {}

    def fake_rename(oc, op, od, nc, np, nd, link):
        called["args"] = (oc, op, od, nc, np, nd)
        return "/tmp/new_path", link

    monkeypatch.setattr("services.folder_utils.rename_policy_folder", fake_rename)

    update_policy(policy, deal_id=deal.id)

    assert called["args"] == ("Bind", "B1", None, "Bind", "B1", "D")
    assert policy.deal_id == deal.id
    assert policy.drive_folder_link == "/tmp/new_path"


def test_update_policy_allows_unbinding(monkeypatch):
    client = add_client(name="Unbind")

    monkeypatch.setattr("services.policy_service.create_policy_folder", lambda *a, **k: "/tmp/policy")
    monkeypatch.setattr("services.policy_service.open_folder", lambda *a, **k: None)

    policy = add_policy(
        client_id=client.id,
        policy_number="U1",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )

    deal = add_deal(client_id=client.id, start_date=date(2025, 1, 1), description="D")

    monkeypatch.setattr(
        "services.folder_utils.rename_policy_folder",
        lambda *a, **k: ("/tmp/bound", None),
    )
    update_policy(policy, deal_id=deal.id)
    assert policy.deal_id == deal.id

    called = {}

    def fake_rename(oc, op, od, nc, np, nd, link):
        called["args"] = (oc, op, od, nc, np, nd)
        return "/tmp/unbound", link

    monkeypatch.setattr("services.folder_utils.rename_policy_folder", fake_rename)

    update_policy(policy, deal_id=None)

    assert called["args"] == (client.name, "U1", "D", client.name, "U1", None)
    assert policy.deal_id is None


def test_update_policy_allows_client_change(monkeypatch):
    c1 = add_client(name="C1")
    c2 = add_client(name="C2")

    monkeypatch.setattr(
        "services.policy_service.create_policy_folder", lambda *a, **k: "/tmp/policy"
    )
    monkeypatch.setattr("services.policy_service.open_folder", lambda *a, **k: None)

    policy = add_policy(
        client_id=c1.id,
        policy_number="CL1",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )

    called = {}

    def fake_rename(oc, op, od, nc, np, nd, link):
        called["args"] = (oc, op, od, nc, np, nd)
        return "/tmp/renamed", link

    monkeypatch.setattr("services.folder_utils.rename_policy_folder", fake_rename)

    update_policy(policy, client_id=c2.id)

    assert called["args"] == (c1.name, "CL1", None, c2.name, "CL1", None)
    assert policy.client_id == c2.id
    assert policy.drive_folder_link == "/tmp/renamed"
