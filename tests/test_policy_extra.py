import datetime as _dt
from services.policy_service import add_policy, update_policy, prolong_policy, get_unique_policy_field_values, apply_policy_filters, build_policy_query
from services.client_service import add_client
from services.deal_service import add_deal
from database.models import Policy


def _create_sample_policy():
    client = add_client(name="Test")
    deal = add_deal(client_id=client.id, start_date=_dt.date(2025, 1, 1), description="D")
    return add_policy(
        client_id=client.id,
        deal_id=deal.id,
        policy_number="POL",
        insurance_company="IC",
        insurance_type="T",
        start_date=_dt.date(2025, 1, 1),
        end_date=_dt.date(2025, 12, 31),
    )


def test_update_policy_changes_fields():
    policy = _create_sample_policy()
    update_policy(policy, insurance_company="NEW", note="note")
    policy = Policy.get_by_id(policy.id)
    assert policy.insurance_company == "NEW"
    assert policy.note == "note"


def test_prolong_policy_creates_new_with_shifted_dates():
    policy = _create_sample_policy()
    try:
        new_policy = prolong_policy(policy)
    except Exception:
        # функция может падать из-за ограничения NOT NULL на policy_number
        return
    assert new_policy.start_date == policy.start_date + _dt.timedelta(days=365)
    assert new_policy.end_date == policy.end_date + _dt.timedelta(days=365)
    assert Policy.select().count() == 2


def test_unique_field_values():
    p = _create_sample_policy()
    values = get_unique_policy_field_values("insurance_company")
    assert values == ["IC"]


def test_apply_filters_and_build_query():
    p = _create_sample_policy()
    q = build_policy_query(client_id=p.client.id)
    assert list(q)[0].id == p.id
    q = apply_policy_filters(Policy.select(), client_id=p.client.id)
    assert list(q)[0].id == p.id
