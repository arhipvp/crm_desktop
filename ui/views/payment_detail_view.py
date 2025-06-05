# ui/views/payment_detail_view.py

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from database.models import Expense, Income, Payment
from services.folder_utils import open_folder
from ui.base.base_table_model import BaseTableModel
from ui.common.date_utils import format_date
from ui.common.styled_widgets import styled_button
from ui.forms.expense_form import ExpenseForm
from ui.forms.income_form import IncomeForm
from ui.forms.payment_form import PaymentForm
from ui.views.expense_detail_view import ExpenseDetailView
from ui.views.income_detail_view import IncomeDetailView


class PaymentDetailView(QDialog):
    """Детальная карточка платежа с вложенными доходами / расходами."""

    def __init__(self, payment: Payment, parent=None):
        super().__init__(parent)
        self.instance = payment
        self.setWindowTitle(f"Платёж #{payment.id} — {payment.amount:.2f} ₽")
        self.resize(900, 650)
        self.setMinimumSize(850, 550)

        self.layout = QVBoxLayout(self)

        # ───── KPI панель ─────
        self._init_kpi_panel()

        # ───── Табы ─────
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs, stretch=1)
        self._init_tabs()
        self._init_actions()

    # ------------------------------------------------------------------
    # KPI
    # ------------------------------------------------------------------
    def _init_kpi_panel(self):
        layout = QHBoxLayout()
        incomes_cnt = Income.select().where(Income.payment == self.instance).count()
        expenses_cnt = Expense.select().where(Expense.payment == self.instance).count()
        layout.addWidget(QLabel(f"Доходов: <b>{incomes_cnt}</b>"))
        layout.addWidget(QLabel(f"Расходов: <b>{expenses_cnt}</b>"))
        layout.addStretch()
        self.layout.addLayout(layout)

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------
    def _init_tabs(self):
        # очистка
        while self.tabs.count():
            w = self.tabs.widget(0)
            self.tabs.removeTab(0)
            w.deleteLater()

        # 1) Информация
        info = QWidget()
        form = QFormLayout(info)
        form.addRow("ID:", QLabel(str(self.instance.id)))
        pol = self.instance.policy
        form.addRow("Полис:", QLabel(f"#{pol.id} {pol.policy_number}" if pol else "—"))
        form.addRow("Сумма:", QLabel(f"{self.instance.amount:.2f} ₽"))
        form.addRow("Плановая дата:", QLabel(format_date(self.instance.payment_date)))
        form.addRow(
            "Фактическая дата:", QLabel(format_date(self.instance.actual_payment_date))
        )
        info.setLayout(form)
        self.tabs.addTab(info, "Информация")

        # 2) Доходы
        inc_tab = QWidget()
        inc_l = QVBoxLayout(inc_tab)
        btn_inc = styled_button("➕ Доход", tooltip="Добавить доход", shortcut="Ctrl+N")
        btn_inc.clicked.connect(self._on_add_income)
        inc_l.addWidget(btn_inc, alignment=Qt.AlignLeft)
        incomes = list(Income.select().where(Income.payment == self.instance))
        inc_l.addWidget(self._make_subtable(incomes, Income, IncomeDetailView))
        self.tabs.addTab(inc_tab, "Доходы")

        # 3) Расходы
        exp_tab = QWidget()
        exp_l = QVBoxLayout(exp_tab)
        btn_exp = styled_button(
            "➕ Расход", tooltip="Добавить расход", shortcut="Ctrl+Shift+N"
        )
        btn_exp.clicked.connect(self._on_add_expense)
        exp_l.addWidget(btn_exp, alignment=Qt.AlignLeft)
        expenses = list(Expense.select().where(Expense.payment == self.instance))
        exp_l.addWidget(self._make_subtable(expenses, Expense, ExpenseDetailView))
        self.tabs.addTab(exp_tab, "Расходы")

    # ------------------------------------------------------------------
    # Bottom actions
    # ------------------------------------------------------------------
    def _init_actions(self):
        row = QHBoxLayout()
        row.addStretch()

        btn_edit = styled_button("✏️ Редактировать", shortcut="Ctrl+E")
        btn_edit.clicked.connect(self._on_edit)
        row.addWidget(btn_edit)

        folder_btn = styled_button("📂 Папка", tooltip="Открыть папку полиса")
        row.addWidget(folder_btn)

        if self.instance.policy:
            btn_open_policy = styled_button("📄 Полис")
            btn_open_policy.clicked.connect(self._open_policy)
            row.addWidget(btn_open_policy)

            pol = self.instance.policy
            pol_path = getattr(pol, "drive_folder_path", None) or pol.drive_folder_link
            if pol_path:
                folder_btn.clicked.connect(lambda: open_folder(pol_path, parent=self))
            else:
                folder_btn.setDisabled(True)
        else:
            folder_btn.setDisabled(True)

        self.layout.addLayout(row)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_edit(self):
        form = PaymentForm(self.instance, parent=self)
        if form.exec():
            self._init_kpi_panel()
            self._init_tabs()

    def _on_add_income(self):
        form = IncomeForm(parent=self)
        self._prefill_payment_in_form(form)
        if form.exec():
            self._init_kpi_panel()
            self._init_tabs()

    def _on_add_expense(self):
        form = ExpenseForm(parent=self)
        self._prefill_payment_in_form(form)
        if form.exec():
            self._init_kpi_panel()
            self._init_tabs()

    # ------------------------------------------------------------------
    # Utils
    # ------------------------------------------------------------------
    def _make_subtable(self, items: list, model_cls, detail_cls):
        table = QTableView()
        model = BaseTableModel(items, model_cls)
        table.setModel(model)
        table.setSortingEnabled(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.doubleClicked.connect(
            lambda idx: detail_cls(model.get_item(idx.row()), parent=self).exec()
        )
        return table

    def _prefill_payment_in_form(self, form):
        if hasattr(form, "prefill_payment"):
            form.prefill_payment(self.instance.id)

    def _open_policy(self):
        if self.instance.policy:
            from ui.views.policy_detail_view import PolicyDetailView

            dlg = PolicyDetailView(self.instance.policy, parent=self)
            dlg.exec()
