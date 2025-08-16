import datetime
import pytest
from peewee import SqliteDatabase
from PySide6.QtWidgets import QApplication, QComboBox
from PySide6.QtCore import QDate

from database.db import db
from database.models import Client, Deal, Policy
from ui.forms.policy_merge_dialog import PolicyMergeDialog
from ui.common.date_utils import OptionalDateEdit


def _create_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _find_row(dlg: PolicyMergeDialog, field: str) -> int:
    for row in range(dlg.table.rowCount()):
        item = dlg.table.item(row, 0)
        if item and item.data(Qt.UserRole) == field:
            return row
    raise AssertionError(f"Row {field} not found")


def test_policy_merge_dialog_display_and_filter():
    _create_app()
    existing = Policy(
        policy_number="P1",
        insurance_company="Old",
        start_date=datetime.date(2024, 1, 1),
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
    test_db.create_tables([Client, Deal, Policy])
    yield
    test_db.drop_tables([Client, Deal, Policy])
    test_db.close()


def test_merge_dialog_dates_and_combos(setup_db):
    _create_app()
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
