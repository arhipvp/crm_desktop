from ui.base.base_detail_view import BaseDetailView
from database.models import Income

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout
from ui.common.styled_widgets import styled_button


class IncomeDetailView(BaseDetailView):
    def __init__(self, income: Income, parent=None):
        super().__init__(income, parent=parent)
        layout = self.layout

        row = QHBoxLayout()
        row.addStretch()

        if income.payment:
            btn_open_payment = styled_button("💳 Платёж")
            btn_open_payment.clicked.connect(self._open_payment)
            row.addWidget(btn_open_payment)

        layout.addLayout(row)

    def _open_payment(self):
        from ui.views.payment_detail_view import PaymentDetailView
        dlg = PaymentDetailView(self.instance.payment, parent=self)
        dlg.exec()
