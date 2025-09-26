# ui/views/policy_detail_view.py

from __future__ import annotations

import base64

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QTabWidget,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from database.models import Expense, Income, Payment, Policy
from services.folder_utils import open_folder
from services.payment_service import get_payments_by_policy_id
from services.income_service import build_income_query
from services.expense_service import build_expense_query
from ui import settings as ui_settings
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

    SETTINGS_KEY = "policy_detail_view"

    def __init__(self, policy: Policy, parent=None):
        super().__init__(parent)
        self.instance = policy
        self.setWindowTitle(
            f"Полис id={policy.id} №{policy.policy_number or ''}"
        )
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
        self._init_kpi_panel()

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
        self._init_tabs()

        # ───────────────────── Кнопки действий ─────────────────
        self._init_actions()

        self._apply_default_splitter_sizes(size.width())
        self._restore_splitter_state()

    # ---------------------------------------------------------------------
    # UI helpers
    # ---------------------------------------------------------------------
    def _init_kpi_panel(self):
        """Короткая статистика сверху окна."""
        while self.kpi_layout.count():
            item = self.kpi_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        cnt_payments = get_payments_by_policy_id(self.instance.id).count()
        cnt_incomes = (
            build_income_query()
            .where(Income.payment.policy == self.instance.id)
            .count()
        )
        cnt_expenses = (
            build_expense_query().where(Expense.policy == self.instance.id).count()
        )
        for text in [
            f"Платежей: <b>{cnt_payments}</b>",
            f"Доходов: <b>{cnt_incomes}</b>",
            f"Расходов: <b>{cnt_expenses}</b>",
        ]:
            lbl = QLabel(text)
            lbl.setTextFormat(Qt.RichText)
            self.kpi_layout.addWidget(lbl)
        self.kpi_layout.addStretch()

    def _init_tabs(self):
        self._populate_summary()

        while self.tabs.count():
            w = self.tabs.widget(0)
            self.tabs.removeTab(0)
            w.deleteLater()

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

    def closeEvent(self, event):
        self._save_splitter_state()
        super().closeEvent(event)

    def _populate_summary(self) -> None:
        rows = [
            ("ID", str(self.instance.id)),
            ("Клиент", self.instance.client.name),
        ]
        if self.instance.deal:
            rows.append(("Сделка", str(self.instance.deal.description)))
        rows.extend(
            [
                ("Номер", self.instance.policy_number or "—"),
                ("Компания", self.instance.insurance_company or "—"),
                ("Тип", self.instance.insurance_type or "—"),
                ("Старт", format_date(self.instance.start_date)),
                ("Окончание", format_date(self.instance.end_date)),
            ]
        )

        while self.summary_layout.rowCount():
            self.summary_layout.removeRow(0)

        title = self.instance.policy_number or "Без номера"
        client_name = self.instance.client.name
        self.header_label.setText(f"Полис {title} — {client_name}")

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
