from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QHBoxLayout, QWidget

from database.models import Payment
from ui.common.date_utils import format_date
from ui.views.payment_detail_view import PaymentDetailView


class PaymentCard(QWidget):
    """Небольшой виджет для отображения сведений о платеже."""

    def __init__(self, payment: Payment, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.instance = payment

        layout = QHBoxLayout(self)

        policy = payment.policy
        policy_number = policy.policy_number if policy else "—"
        layout.addWidget(QLabel(f"Полис: {policy_number}"))

        layout.addWidget(QLabel(f"Сумма: {payment.amount:.2f} ₽"))
        layout.addWidget(QLabel(f"Плановая: {format_date(payment.payment_date)}"))
        layout.addWidget(
            QLabel(f"Фактическая: {format_date(payment.actual_payment_date)}")
        )
        layout.addStretch()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            dlg = PaymentDetailView(self.instance, parent=self)
            dlg.exec()
        super().mouseReleaseEvent(event)


__all__ = ["PaymentCard"]
