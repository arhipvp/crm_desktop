import datetime
import pytest
from peewee import SqliteDatabase
from PySide6.QtTest import QTest
from PySide6.QtGui import QDoubleValidator

from database.db import db
from database.models import Client, Deal, Policy, Payment
from ui.forms.policy_form import PolicyForm
from ui.forms.policy_merge_dialog import PolicyMergeDialog


@pytest.fixture()
def setup_db():
    test_db = SqliteDatabase(':memory:')
    db.initialize(test_db)
    test_db.create_tables([Client, Deal, Policy, Payment])
    yield
    test_db.drop_tables([Client, Deal, Policy, Payment])
    test_db.close()


def test_pay_amount_validator_policy_form_blocks_letters(qapp, setup_db):
    Client.create(name="C")
    form = PolicyForm()
    edit = form.pay_amount_edit
    validator = edit.validator()
    assert isinstance(validator, QDoubleValidator)
    assert validator.bottom() == 0.0
    assert validator.top() == 1e9
    assert validator.decimals() == 2
    edit.setFocus()
    QTest.keyClicks(edit, "abc")
    assert edit.text() == ""
def test_pay_amount_validator_merge_dialog_blocks_letters(qapp, setup_db):
    client = Client.create(name="C")
    policy = Policy.create(client=client, policy_number="P", start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 12, 31))
    dlg = PolicyMergeDialog(policy, {})
    edit = dlg.pay_amount_edit
    validator = edit.validator()
    assert isinstance(validator, QDoubleValidator)
    assert validator.bottom() == 0.0
    assert validator.top() == 1e9
    assert validator.decimals() == 2
    edit.setFocus()
    QTest.keyClicks(edit, "abc")
    assert edit.text() == ""
