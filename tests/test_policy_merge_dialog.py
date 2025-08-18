import datetime
import pytest
from peewee import SqliteDatabase
from PySide6.QtWidgets import QComboBox
from PySide6.QtCore import QDate, Qt

from database.db import db
from database.models import Client, Deal, Policy, Payment, Income, Expense
from services.policy_service import update_policy
from ui.forms.policy_merge_dialog import PolicyMergeDialog
from ui.common.date_utils import OptionalDateEdit


def _find_row(dlg: PolicyMergeDialog, field: str) -> int:
    for row in range(dlg.table.rowCount()):
        item = dlg.table.item(row, 0)
        if item and item.data(Qt.UserRole) == field:
            return row
    raise AssertionError(f"Row {field} not found")


def test_policy_merge_dialog_display_and_filter(qapp, setup_db):
    client = Client.create(name="C")
    existing = Policy.create(
        client=client,
        policy_number="P1",
        insurance_company="Old",
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 12, 31),
    )
    new_data = {
        "policy_number": "P1",
        "insurance_company": "New",
        "start_date": datetime.date(2024, 1, 1),
    }
    dlg = PolicyMergeDialog(existing, new_data)
    assert dlg.table.rowCount() == 3

    row_ins = _find_row(dlg, "insurance_company")
    row_num = _find_row(dlg, "policy_number")

    assert not dlg.table.isRowHidden(row_ins)
    assert not dlg.table.isRowHidden(row_num)

    color_changed = dlg.table.item(row_ins, 3).background().color()
    assert color_changed.isValid() and color_changed.name().lower() == "#fff0b3"

    color_unchanged = dlg.table.item(row_num, 3).background().color()
    assert not color_unchanged.isValid()

    dlg.show_only_changes_cb.setChecked(True)
    assert not dlg.table.isRowHidden(row_ins)
    assert dlg.table.isRowHidden(row_num)


@pytest.fixture()
def setup_db():
    test_db = SqliteDatabase(':memory:')
    db.initialize(test_db)
    test_db.create_tables([Client, Deal, Policy, Payment, Income, Expense])
    yield
    test_db.drop_tables([Client, Deal, Policy, Payment, Income, Expense])
    test_db.close()


def test_merge_dialog_dates_and_combos(qapp, setup_db):
    c1 = Client.create(name='Old')
    c2 = Client.create(name='New')
    deal = Deal.create(client=c2, description='D', start_date=datetime.date(2024, 1, 1))
    existing = Policy.create(client=c1, policy_number='P', start_date=datetime.date(2024, 1, 1))
    new_data = {
        'client_id': c2.id,
        'deal_id': deal.id,
        'start_date': datetime.date(2024, 1, 1),
        'end_date': datetime.date(2024, 2, 1),
    }
    dlg = PolicyMergeDialog(existing, new_data)

    row_client = _find_row(dlg, 'client_id')
    client_combo = dlg.table.cellWidget(row_client, 2)
    assert isinstance(client_combo, QComboBox)
    client_combo.setCurrentIndex(client_combo.findData(c2.id))

    row_deal = _find_row(dlg, 'deal_id')
    deal_combo = dlg.table.cellWidget(row_deal, 2)
    assert isinstance(deal_combo, QComboBox)
    deal_combo.setCurrentIndex(deal_combo.findData(deal.id))

    row_start = _find_row(dlg, 'start_date')
    start_edit = dlg.table.cellWidget(row_start, 2)
    assert isinstance(start_edit, OptionalDateEdit)
    start_edit.setDate(QDate(2025, 1, 1))

    row_end = _find_row(dlg, 'end_date')
    end_edit = dlg.table.cellWidget(row_end, 2)
    assert isinstance(end_edit, OptionalDateEdit)
    end_edit.setDate(QDate(2025, 2, 1))

    data = dlg.get_merged_data()
    assert data['client_id'] == c2.id
    assert data['deal_id'] == deal.id
    assert data['start_date'] == datetime.date(2025, 1, 1)
    assert data['end_date'] == datetime.date(2025, 2, 1)


def test_client_change_filters_deals(qapp, setup_db):
    c1 = Client.create(name="C1")
    c2 = Client.create(name="C2")
    d1 = Deal.create(client=c1, description="D1", start_date=datetime.date(2024, 1, 1))
    d2 = Deal.create(client=c2, description="D2", start_date=datetime.date(2024, 1, 1))
    existing = Policy.create(client=c1, policy_number="P", start_date=datetime.date(2024, 1, 1))
    new_data = {"client_id": c1.id, "deal_id": d1.id}
    dlg = PolicyMergeDialog(existing, new_data)

    row_client = _find_row(dlg, "client_id")
    client_combo = dlg.table.cellWidget(row_client, 2)
    row_deal = _find_row(dlg, "deal_id")
    deal_combo = dlg.table.cellWidget(row_deal, 2)
    assert isinstance(client_combo, QComboBox)
    assert isinstance(deal_combo, QComboBox)

    ids_before = {deal_combo.itemData(i) for i in range(deal_combo.count())}
    assert d1.id in ids_before and d2.id not in ids_before

    client_combo.setCurrentIndex(client_combo.findData(c2.id))
    ids_after = {deal_combo.itemData(i) for i in range(deal_combo.count())}
    assert d2.id in ids_after and d1.id not in ids_after


def test_merge_dialog_payments_editing(qapp, setup_db):
    c = Client.create(name="C")
    start = datetime.date(2024, 1, 1)
    end = datetime.date(2024, 12, 31)
    policy = Policy.create(client=c, policy_number="P", start_date=start, end_date=end)
    Payment.create(policy=policy, amount=100, payment_date=start)
    Payment.create(policy=policy, amount=200, payment_date=start + datetime.timedelta(days=30))

    draft = [
        {"payment_date": start + datetime.timedelta(days=60), "amount": 300},
        {"payment_date": start + datetime.timedelta(days=90), "amount": 400},
    ]

    dlg = PolicyMergeDialog(policy, {}, draft_payments=draft)
    assert dlg.payments_table.rowCount() == 4

    # Удаляем один существующий платёж и один из черновиков
    dlg.on_delete_payment(1)  # удаляем платёж 200
    dlg.on_delete_payment(2)  # удаляем черновой платёж 400

    new_date = start + datetime.timedelta(days=120)
    dlg.pay_date_edit.setDate(QDate(new_date.year, new_date.month, new_date.day))
    dlg.pay_amount_edit.setText("500")
    dlg.on_add_payment()

    dlg.first_payment_checkbox.setChecked(True)

    payments = dlg.get_merged_payments()
    amounts = sorted(p["amount"] for p in payments)
    assert amounts == [100, 300, 500]

    update_policy(policy, payments=payments, first_payment_paid=True)
    stored = list(policy.payments.order_by(Payment.payment_date))
    assert [p.amount for p in stored] == [100, 300, 500]
    assert stored[0].actual_payment_date == stored[0].payment_date
    # Проверяем, что платёж 200 удалён
    assert (
        Payment.select()
        .where((Payment.policy == policy) & (Payment.amount == 200))
        .count()
        == 0
    )
