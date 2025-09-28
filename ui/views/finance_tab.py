from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from ui.views.expense_table_view import ExpenseTableView
from ui.views.income_table_view import IncomeTableView
from ui.views.payment_table_view import PaymentTableView


class FinanceTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)

        self.payment_view = PaymentTableView()
        self.income_view = IncomeTableView()
        self.expense_view = ExpenseTableView()

        self.tabs.addTab(self.payment_view, "Платежи")
        self.tabs.addTab(self.income_view, "Доходы")
        self.tabs.addTab(self.expense_view, "Расходы")

        self.tabs.setCurrentIndex(0)
