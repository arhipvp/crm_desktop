from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from core.app_context import AppContext
from ui.views.expense_table_view import ExpenseTableView
from ui.views.income_table_view import IncomeTableView
from ui.views.payment_table_view import PaymentTableView


class FinanceTab(QWidget):
    def __init__(
        self,
        parent=None,
        *,
        context: AppContext | None = None,
        payment_view_factory=PaymentTableView,
        income_view_factory=IncomeTableView,
        expense_view_factory=ExpenseTableView,
    ):
        super().__init__(parent)
        self._context = context

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)

        self.payment_view = payment_view_factory(
            parent=self, context=self._context
        )
        self.income_view = income_view_factory(parent=self, context=self._context)
        self.expense_view = expense_view_factory(parent=self, context=self._context)

        self.tabs.addTab(self.payment_view, "Платежи")
        self.tabs.addTab(self.income_view, "Доходы")
        self.tabs.addTab(self.expense_view, "Расходы")

        self.tabs.setCurrentIndex(0)
