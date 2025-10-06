from datetime import date
from decimal import Decimal

import pytest

from services import payment_service
from database.db import db
from database.models import Payment
from utils.filter_constants import CHOICE_NULL_TOKEN


@pytest.mark.usefixtures("db_transaction")
def test_update_payment_with_nonexistent_policy_raises_value_error(
    make_policy_with_payment,
):
    _, _, policy, payment = make_policy_with_payment()
    nonexistent_policy_id = policy.id + 1

    with pytest.raises(ValueError, match="Полис с id="):
        payment_service.update_payment(payment, policy_id=nonexistent_policy_id)

    reloaded_payment = Payment.get_by_id(payment.id)
    assert reloaded_payment.policy_id == policy.id


def test_payment_service_filters_null_actual_payment_date(
    make_policy_with_payment,
):
    _, _, _, unpaid = make_policy_with_payment(
        policy_kwargs={"policy_number": "PM-UNPAID"},
        payment_kwargs={"actual_payment_date": None},
    )
    _, _, _, paid = make_policy_with_payment(
        policy_kwargs={"policy_number": "PM-PAID"},
        payment_kwargs={"actual_payment_date": date(2024, 5, 20)},
    )

    query = payment_service.get_payments_page(
        1,
        20,
        column_filters={"actual_payment_date": [CHOICE_NULL_TOKEN]},
    )
    results = list(query)

    assert {payment.id for payment in results} == {unpaid.id}

    mixed_query = payment_service.get_payments_page(
        1,
        20,
        column_filters={
            "actual_payment_date": [
                CHOICE_NULL_TOKEN,
                paid.actual_payment_date.isoformat(),
            ]
        },
    )
    mixed_results = list(mixed_query)
    assert {payment.id for payment in mixed_results} == {unpaid.id, paid.id}


@pytest.mark.usefixtures("db_transaction")
def test_get_payment_amounts_by_deal_id_single_query(
    make_policy_with_payment, monkeypatch
):
    """Суммы платежей считаются одним SQL-запросом."""

    client, deal, policy, _open_payment = make_policy_with_payment(
        payment_kwargs={"amount": 100, "actual_payment_date": None}
    )
    make_policy_with_payment(
        client=client,
        deal=deal,
        policy_kwargs={"policy_number": f"{policy.policy_number}-2"},
        payment_kwargs={
            "amount": 150,
            "actual_payment_date": date(2024, 1, 15),
        },
    )
    make_policy_with_payment(
        client=client,
        deal=deal,
        policy_kwargs={"policy_number": f"{policy.policy_number}-3"},
        payment_kwargs={"amount": 200, "actual_payment_date": None},
    )

    database = db.obj
    executed: list[str] = []
    original_execute_sql = database.execute_sql

    def spy(sql, params=None, *args, **kwargs):
        executed.append(sql)
        return original_execute_sql(sql, params, *args, **kwargs)

    monkeypatch.setattr(database, "execute_sql", spy)

    expected, received = payment_service.get_payment_amounts_by_deal_id(deal.id)

    assert expected == Decimal("300")
    assert received == Decimal("150")
    assert len(executed) == 1
