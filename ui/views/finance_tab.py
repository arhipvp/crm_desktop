# ui/views/finance_tab.py

from PySide6.QtWidgets import QWidget, QTabWidget, QVBoxLayout
from ui.views.payment_table_view import PaymentTableView
from ui.views.income_table_view import IncomeTableView
from ui.views.expense_table_view import ExpenseTableView


class FinanceTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        tabs.addTab(PaymentTableView(), "Платежи")
        tabs.addTab(IncomeTableView(), "Доходы")
        tabs.addTab(ExpenseTableView(), "Расходы")

        layout.addWidget(tabs)
        self.setLayout(layout)
