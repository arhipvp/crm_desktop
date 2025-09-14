# ui/views/policy_detail_view.py

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHeaderView,
    QLabel,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QTableView,
)

from database.models import Expense, Income, Payment, Policy
from services.folder_utils import open_folder
from services.payment_service import get_payments_by_policy_id
from services.income_service import build_income_query
from services.expense_service import build_expense_query
from ui.base.base_table_model import BaseTableModel
from ui.common.date_utils import format_date
from ui.common.styled_widgets import styled_button
from utils.screen_utils import get_scaled_size
from ui.forms.payment_form import PaymentForm
from ui.forms.policy_form import PolicyForm
from ui.views.payment_detail_view import PaymentDetailView
from ui.views.income_detail_view import IncomeDetailView
from ui.views.expense_detail_view import ExpenseDetailView


class PolicyDetailView(QDialog):
    """Детальная карточка полиса.

    Вкладки:
        • Информация
        • Платежи (с кнопкой «добавить»)
        • Доходы
        • Расходы
    """

    def __init__(self, policy: Policy, parent=None):
        super().__init__(parent)
        self.instance = policy
        self.setWindowTitle(
            f"Полис id={policy.id} №{policy.policy_number or ''}"
        )
        size = get_scaled_size(1000, 700)
        self.resize(size)
        self.setMinimumSize(640, 480)

        self.layout = QVBoxLayout(self)

        # ───────────────────── KPI панель ──────────────────────
        self._init_kpi_panel()

        # ───────────────────── Вкладки ─────────────────────────
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs, stretch=1)
        self._init_tabs()

        # ───────────────────── Кнопки действий ─────────────────
        self._init_actions()

    # ---------------------------------------------------------------------
    # UI helpers
    # ---------------------------------------------------------------------
    def _init_kpi_panel(self):
        """Короткая статистика сверху окна."""
        kpi = QHBoxLayout()
        cnt_payments = get_payments_by_policy_id(self.instance.id).count()
        cnt_incomes = (
            build_income_query()
            .where(Income.payment.policy == self.instance.id)
            .count()
        )
        cnt_expenses = (
            build_expense_query().where(Expense.policy == self.instance.id).count()
        )
        kpi.addWidget(QLabel(f"Платежей: <b>{cnt_payments}</b>"))
        kpi.addWidget(QLabel(f"Доходов: <b>{cnt_incomes}</b>"))
        kpi.addWidget(QLabel(f"Расходов: <b>{cnt_expenses}</b>"))
        kpi.addStretch()
        self.layout.addLayout(kpi)

    def _init_tabs(self):
        # ——— Информация ————————————————————————————
        info = QWidget()
        form = QFormLayout(info)
        form.addRow("ID:", QLabel(str(self.instance.id)))
        form.addRow("Клиент:", QLabel(self.instance.client.name))
        if self.instance.deal:
            form.addRow("Сделка:", QLabel(str(self.instance.deal.description)))
        form.addRow("Номер полиса:", QLabel(self.instance.policy_number or "—"))
        form.addRow("Компания:", QLabel(self.instance.insurance_company or "—"))
        form.addRow("Тип страхования:", QLabel(self.instance.insurance_type or "—"))
        form.addRow("Старт:", QLabel(format_date(self.instance.start_date)))
        form.addRow("Окончание:", QLabel(format_date(self.instance.end_date)))
        note = QTextEdit(self.instance.note or "")
        note.setReadOnly(True)
        note.setFixedHeight(70)
        form.addRow("Примечание:", note)
        info.setLayout(form)
        self.tabs.addTab(info, "Информация")

        # ——— Платежи ————————————————————————————
        pay_tab = QWidget()
        pay_l = QVBoxLayout(pay_tab)
        btn_add_payment = styled_button(
            "➕ Платёж", tooltip="Добавить платёж", shortcut="Ctrl+N"
        )
        btn_add_payment.clicked.connect(self._on_add_payment)
        pay_l.addWidget(btn_add_payment, alignment=Qt.AlignLeft)
        payments = list(get_payments_by_policy_id(self.instance.id))
        pay_l.addWidget(self._make_subtable(payments, Payment, PaymentDetailView))
        self.tabs.addTab(pay_tab, "Платежи")

        # ——— Доходы ————————————————————————————
        inc_tab = QWidget()
        inc_l = QVBoxLayout(inc_tab)
        incomes = list(
            build_income_query().where(Income.payment.policy == self.instance.id)
        )
        inc_l.addWidget(self._make_subtable(incomes, Income, IncomeDetailView))
        self.tabs.addTab(inc_tab, "Доходы")

        # ——— Расходы ————————————————————————————
        exp_tab = QWidget()
        exp_l = QVBoxLayout(exp_tab)
        expenses = list(build_expense_query().where(Expense.policy == self.instance.id))
        exp_l.addWidget(self._make_subtable(expenses, Expense, ExpenseDetailView))
        self.tabs.addTab(exp_tab, "Расходы")

    def _init_actions(self):
        row = QHBoxLayout()
        row.addStretch()
        btn_edit = styled_button("✏️ Редактировать", shortcut="Ctrl+E")
        btn_edit.clicked.connect(self._on_edit)
        row.addWidget(btn_edit)
        if getattr(self.instance, "drive_folder_path", None) or self.instance.drive_folder_link:
            btn_folder = styled_button("📂 Папка")
            btn_folder.clicked.connect(self._open_folder)
            row.addWidget(btn_folder)
        self.layout.addLayout(row)

    # ------------------------------------------------------------------
    # Slots / callbacks
    # ------------------------------------------------------------------
    def _on_edit(self):
        form = PolicyForm(self.instance, parent=self)
        if form.exec():
            # Перерисовать всё, если пользователь сохранил изменения
            self._init_kpi_panel()
            self._init_tabs()

    def _on_add_payment(self):
        form = PaymentForm(parent=self, forced_policy=self.instance)
        if form.exec():
            self._init_tabs()
        # если форма поддерживает префилл полиса
        if hasattr(form, "fields") and "policy_id" in form.fields:
            combo = form.fields["policy_id"]
            if combo.currentData() != self.instance.id:
                idx = combo.findData(self.instance.id)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
        if form.exec():
            self._init_kpi_panel()
            self._init_tabs()

    def _open_folder(self):
        open_folder(
            getattr(self.instance, "drive_folder_path", None)
            or self.instance.drive_folder_link,
            parent=self,
        )

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
