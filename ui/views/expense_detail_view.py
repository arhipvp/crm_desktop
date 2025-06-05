from PySide6.QtWidgets import QHBoxLayout

from database.models import Expense
from ui.base.base_detail_view import BaseDetailView
from ui.common.styled_widgets import styled_button


class ExpenseDetailView(BaseDetailView):
    def __init__(self, expense: Expense, parent=None):
        super().__init__(expense, parent=parent)
        layout = self.layout

        row = QHBoxLayout()
        row.addStretch()

        if expense.payment:
            btn_open_payment = styled_button("💳 Платёж")
            btn_open_payment.clicked.connect(self._open_payment)
            row.addWidget(btn_open_payment)

        layout.addLayout(row)

    def _open_payment(self):
        from ui.views.payment_detail_view import PaymentDetailView  # локальный импорт

        dlg = PaymentDetailView(self.instance.payment, parent=self)
        dlg.exec()
