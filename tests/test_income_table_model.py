import datetime
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush

from database.models import Policy, Payment, Income
from ui.views.income_table_view import IncomeTableModel

def test_row_highlight_with_contractor(qapp):
    policy = Policy(policy_number="123", contractor="Some Corp", start_date=datetime.date.today())
    payment = Payment(policy=policy, amount=100, payment_date=datetime.date.today())
    income = Income(payment=payment, amount=10, received_date=datetime.date.today())
    model = IncomeTableModel([income], Income)
    idx = model.index(0, 0)
    brush = model.data(idx, Qt.BackgroundRole)
    assert isinstance(brush, QBrush)

def test_row_no_highlight_without_contractor(qapp):
    policy = Policy(policy_number="456", contractor=None, start_date=datetime.date.today())
    payment = Payment(policy=policy, amount=100, payment_date=datetime.date.today())
    income = Income(payment=payment, amount=10, received_date=datetime.date.today())
    model = IncomeTableModel([income], Income)
    idx = model.index(0, 0)
    assert model.data(idx, Qt.BackgroundRole) is None
