# ui/views/payment_detail_view.py

from __future__ import annotations

import base64

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QSplitter,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from database.models import Expense, Income, Payment
from services.folder_utils import open_folder
from ui import settings as ui_settings
from ui.base.base_table_model import BaseTableModel
from ui.common.date_utils import format_date
from ui.common.styled_widgets import styled_button
from utils.screen_utils import get_scaled_size
from ui.forms.expense_form import ExpenseForm
from ui.forms.income_form import IncomeForm
from ui.forms.payment_form import PaymentForm
from ui.views.expense_detail_view import ExpenseDetailView
from ui.views.income_detail_view import IncomeDetailView


class PaymentDetailView(QDialog):
    """Детальная карточка платежа с вложенными доходами / расходами."""

    SETTINGS_KEY = "payment_detail_view"

    def __init__(self, payment: Payment, parent=None):
        super().__init__(parent)
        self.instance = payment
        self.setWindowTitle(f"Платёж #{payment.id} — {payment.amount:.2f} ₽")
        size = get_scaled_size(1100, 720)
        self.resize(size)
        self.setMinimumSize(800, 600)

        self.layout = QVBoxLayout(self)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.layout.addWidget(self.splitter, stretch=1)

        self.left_panel = QWidget()
        self.left_panel.setMinimumWidth(260)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        self.header_label = QLabel()
        self.header_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.header_label.setWordWrap(True)
        left_layout.addWidget(self.header_label)

        self.kpi_container = QWidget()
        self.kpi_layout = QHBoxLayout(self.kpi_container)
        self.kpi_layout.setContentsMargins(0, 0, 0, 0)
        self.kpi_layout.setSpacing(8)
        left_layout.addWidget(self.kpi_container)

        self.summary_widget = QWidget()
        self.summary_layout = QFormLayout(self.summary_widget)
        self.summary_layout.setLabelAlignment(Qt.AlignRight)
        self.summary_layout.setHorizontalSpacing(12)
        left_layout.addWidget(self.summary_widget, stretch=1)
        left_layout.addStretch()

        self.splitter.addWidget(self.left_panel)

        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.splitter.addWidget(self.tabs)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

        # ссылки на KPI-панель
        self._lbl_incomes: QLabel | None = None
        self._lbl_expenses: QLabel | None = None

        # ───── KPI панель ─────
        self._init_kpi_panel()

        # ───── Табы ─────
        self._init_tabs()
        self._init_actions()

        self._apply_default_splitter_sizes(size.width())
        self._restore_splitter_state()

    # ------------------------------------------------------------------
    # KPI
    # ------------------------------------------------------------------
    def _init_kpi_panel(self):
        incomes_cnt = Income.select().where(Income.payment == self.instance).count()
        expenses_cnt = Expense.select().where(Expense.payment == self.instance).count()

        while self.kpi_layout.count():
            item = self.kpi_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self._lbl_incomes = QLabel(f"Доходов: <b>{incomes_cnt}</b>")
        self._lbl_expenses = QLabel(f"Расходов: <b>{expenses_cnt}</b>")
        for lbl in (self._lbl_incomes, self._lbl_expenses):
            lbl.setTextFormat(Qt.RichText)
            self.kpi_layout.addWidget(lbl)
        self.kpi_layout.addStretch()

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------
    def _init_tabs(self):
        self._populate_summary()

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
        form.addRow(
            "Полис:",
            QLabel(f"id={pol.id} №{pol.policy_number}" if pol else "—"),
        )
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

    def closeEvent(self, event):
        self._save_splitter_state()
        super().closeEvent(event)

    def _populate_summary(self) -> None:
        policy = self.instance.policy
        policy_text = (
            f"id={policy.id} №{policy.policy_number}" if policy else "—"
        )
        rows = [
            ("ID", str(self.instance.id)),
            ("Полис", policy_text),
            ("Сумма", f"{self.instance.amount:.2f} ₽"),
            ("Плановая дата", format_date(self.instance.payment_date)),
            (
                "Фактическая дата",
                format_date(self.instance.actual_payment_date),
            ),
        ]

        while self.summary_layout.rowCount():
            self.summary_layout.removeRow(0)

        self.header_label.setText(f"Платёж #{self.instance.id}")

        for label, value in rows:
            widget = QLabel(value)
            widget.setTextFormat(Qt.RichText)
            widget.setWordWrap(True)
            self.summary_layout.addRow(f"{label}:", widget)

    def _apply_default_splitter_sizes(self, total_width: int | None = None) -> None:
        total = total_width or self.width() or 1
        left = int(total * 0.35)
        right = max(1, total - left)
        self.splitter.setSizes([left, right])

    def _restore_splitter_state(self) -> None:
        state = ui_settings.get_window_settings(self.SETTINGS_KEY).get("splitter_state")
        if state:
            try:
                self.splitter.restoreState(base64.b64decode(state))
                return
            except Exception:
                pass
        self._apply_default_splitter_sizes()

    def _save_splitter_state(self) -> None:
        st = ui_settings.get_window_settings(self.SETTINGS_KEY)
        st["splitter_state"] = base64.b64encode(self.splitter.saveState()).decode("ascii")
        ui_settings.set_window_settings(self.SETTINGS_KEY, st)

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
