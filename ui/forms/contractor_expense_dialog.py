from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from database.models import Expense, Payment, Policy


@dataclass(slots=True)
class _PaymentRow:
    payment: Payment
    expenses: list[Expense]
    checkbox: QCheckBox


class ContractorExpenseDialog(QDialog):
    """Диалог выбора платежей для создания расходов контрагенту."""

    def __init__(self, policy: Policy, contractor_name: str, parent=None):
        super().__init__(parent)
        self.policy = policy
        self.contractor_name = contractor_name
        self.setWindowTitle("Расходы для контрагента")
        self.setMinimumSize(520, 360)

        layout = QVBoxLayout(self)

        info_label = QLabel(
            "Выберите платежи, для которых нужно создать или обновить расходы "
            f"контрагенту «{contractor_name}»."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Дата платежа", "Сумма", "Статус расхода", "Выбрать"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        layout.addWidget(self.table)

        self._rows: list[_PaymentRow] = []
        self._populate_table()

        controls = QHBoxLayout()
        select_all_btn = QPushButton("Выбрать все")
        select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        select_none_btn = QPushButton("Снять выделение")
        select_none_btn.clicked.connect(lambda: self._set_all_checked(False))
        controls.addStretch()
        controls.addWidget(select_all_btn)
        controls.addWidget(select_none_btn)
        layout.addLayout(controls)

        buttons = QHBoxLayout()
        self.ok_btn = QPushButton("Создать расходы")
        self.ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(self.ok_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        if not self._rows:
            self.ok_btn.setEnabled(False)
            empty_label = QLabel("У полиса нет активных платежей.")
            empty_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(empty_label)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _populate_table(self) -> None:
        payments = list(
            Payment.active()
            .where(Payment.policy == self.policy)
            .order_by(Payment.payment_date)
        )
        payment_ids = [payment.id for payment in payments]
        expenses_map: dict[int, list[Expense]] = {pid: [] for pid in payment_ids}

        if payment_ids:
            expenses_query = (
                Expense.active()
                .where(
                    (Expense.payment_id.in_(payment_ids))
                    & (Expense.expense_type == "контрагент")
                )
            )
            for expense in expenses_query:
                expenses_map.setdefault(expense.payment_id, []).append(expense)

        for payment in payments:
            row = self.table.rowCount()
            self.table.insertRow(row)

            date_item = QTableWidgetItem(self._format_date(payment.payment_date))
            date_item.setData(Qt.UserRole, payment.id)
            self.table.setItem(row, 0, date_item)

            amount_item = QTableWidgetItem(self._format_amount(payment.amount))
            self.table.setItem(row, 1, amount_item)

            expenses = expenses_map.get(payment.id, [])
            status_item = QTableWidgetItem(self._describe_expenses(expenses))
            self.table.setItem(row, 2, status_item)

            checkbox = QCheckBox()
            checkbox.setChecked(True)
            self.table.setCellWidget(row, 3, checkbox)

            self._rows.append(_PaymentRow(payment=payment, expenses=expenses, checkbox=checkbox))

        self.table.resizeColumnsToContents()

    @staticmethod
    def _format_date(value: date | None) -> str:
        return value.strftime("%d.%m.%Y") if isinstance(value, date) else "—"

    @staticmethod
    def _format_amount(value: Decimal | float | int | None) -> str:
        if value is None:
            return "0.00"
        try:
            return f"{Decimal(str(value)):.2f}"
        except Exception:
            return str(value)

    @staticmethod
    def _describe_expenses(expenses: Iterable[Expense]) -> str:
        expenses = list(expenses)
        if not expenses:
            return "—"
        descriptions = []
        for expense in expenses:
            if expense.expense_date:
                descriptions.append(expense.expense_date.strftime("%d.%m.%Y"))
            else:
                descriptions.append("без даты")
        return "Есть: " + ", ".join(descriptions)

    def _set_all_checked(self, checked: bool) -> None:
        for row in self._rows:
            row.checkbox.setChecked(checked)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_selected_payments(self) -> list[Payment]:
        return [row.payment for row in self._rows if row.checkbox.isChecked()]

    def get_selected_expenses(self) -> list[Expense]:
        selected_expenses: list[Expense] = []
        for row in self._rows:
            if row.checkbox.isChecked():
                selected_expenses.extend(row.expenses)
        return selected_expenses

