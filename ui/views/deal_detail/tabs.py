from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QLabel,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from database.models import Task
from services.payment_service import get_payments_by_deal_id
from ui.common.date_utils import TypableDateEdit, format_date
from ui.common.styled_widgets import styled_button
from ..calculation_table_view import CalculationTableView
from ..expense_table_view import ExpenseTableView
from ..income_table_view import IncomeTableView
from ..payment_table_view import PaymentTableView
from ..policy_table_view import PolicyTableView
from ..task_table_view import TaskTableView
from .widgets import _CalcHighlighter, _with_day_separators, CollapsibleWidget


class DealTabsMixin:
    def _init_tabs(self):
        # удаляем старые вкладки
        while self.tabs.count():
            w = self.tabs.widget(0)
            self.tabs.removeTab(0)
            w.deleteLater()

        # ---------- Главная вкладка ---------------------------------
        deal_tab = QWidget()
        deal_layout = QVBoxLayout(deal_tab)
        deal_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        info_panel = CollapsibleWidget("Основная информация")
        form = QFormLayout()
        form.setVerticalSpacing(2)
        form.setHorizontalSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        def tight_label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            lbl.setMinimumHeight(1)
            lbl.setTextFormat(Qt.RichText)
            return lbl

        form.addRow("ID:", tight_label(str(self.instance.id)))
        client_html = f"<b>{self.instance.client.name}</b>"
        note = self.instance.client.note
        if note:
            client_html += f" <span style='color:red'>{note}</span>"
        form.addRow("Клиент:", tight_label(client_html))
        form.addRow("Телефон:", tight_label(self.instance.client.phone or "—"))

        start_label = tight_label(format_date(self.instance.start_date))
        form.addRow("Старт:", start_label)

        self.status_edit = QTextEdit(self.instance.status)
        self.status_edit.setFixedHeight(40)
        form.addRow("Статус:", self.status_edit)

        self.desc_edit = QTextEdit(self.instance.description)
        self.desc_edit.setFixedHeight(60)
        self.desc_edit.setReadOnly(True)
        form.addRow("Описание:", self.desc_edit)

        self.reminder_date = TypableDateEdit(self.instance.reminder_date)
        form.addRow("Напоминание:", self.reminder_date)

        info_panel.setContentLayout(form)
        container_layout.addWidget(info_panel)

        journal_panel = CollapsibleWidget("Журнал")
        journal_form = QFormLayout()

        self.calc_append = QTextEdit()
        self.calc_append.setPlaceholderText("Новая запись…")
        self.calc_append.setFixedHeight(50)
        journal_form.addRow("Добавить:", self.calc_append)

        self.calc_view = QTextEdit()
        self.calc_view.setReadOnly(True)
        self.calc_view.setFixedHeight(140)
        self.calc_view.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.calc_view.setPlainText(_with_day_separators(self.instance.calculations))
        self._calc_highlighter = _CalcHighlighter(self.calc_view.document())
        journal_form.addRow("История:", self.calc_view)

        self.btn_exec_task = styled_button("📤 Новая задача исполнителю")
        self.btn_exec_task.clicked.connect(self._on_new_exec_task)

        j_layout = QVBoxLayout()
        j_layout.addLayout(journal_form)
        j_layout.addWidget(self.btn_exec_task, alignment=Qt.AlignLeft)
        journal_panel.setContentLayout(j_layout)
        container_layout.addWidget(journal_panel)

        calc_panel = CollapsibleWidget("Расчёты")
        calc_layout = QVBoxLayout()
        btn_calc = styled_button("➕ Запись", tooltip="Добавить расчёт", shortcut="Ctrl+Shift+A")
        btn_calc.clicked.connect(self._on_add_calculation)
        self._add_shortcut("Ctrl+Shift+A", self._on_add_calculation)
        calc_layout.addWidget(btn_calc, alignment=Qt.AlignLeft)
        self.calc_table = CalculationTableView(parent=self, deal_id=self.instance.id)
        self.calc_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        calc_layout.addWidget(self.calc_table, 1)
        calc_panel.setContentLayout(calc_layout)
        container_layout.addWidget(calc_panel)

        container_layout.addStretch()
        scroll.setWidget(container)
        deal_layout.addWidget(scroll, 1)

        btn_save = styled_button("💾 Сохранить изменения", shortcut="Ctrl+Enter")
        btn_save.clicked.connect(self._on_inline_save)
        self._add_shortcut("Ctrl+Enter", self._on_inline_save)
        btn_save_close = styled_button("💾 Сохранить и закрыть", shortcut="Ctrl+Shift+Enter")
        btn_save_close.clicked.connect(self._on_save_and_close)
        btn_refresh = styled_button("🔄 Обновить", shortcut="F5")
        btn_refresh.clicked.connect(self._on_refresh)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_save_close)
        btn_row.addWidget(btn_refresh)
        deal_layout.addLayout(btn_row)

        self.tabs.addTab(deal_tab, "Сделка")

        # ---------- Полисы -----------------------------------------
        pol_tab = QWidget()
        pol_l = QVBoxLayout(pol_tab)
        hlayout = QHBoxLayout()
        btn_pol = styled_button("➕ Полис", tooltip="Добавить полис", shortcut="Ctrl+N")
        btn_pol.clicked.connect(self._on_add_policy)
        self._add_shortcut("Ctrl+N", self._on_add_policy)
        hlayout.addWidget(btn_pol)
        btn_import = styled_button("📥 Импорт из JSON", tooltip="Импорт полиса по данным")
        btn_import.clicked.connect(self._on_import_policy_json)
        hlayout.addWidget(btn_import)
        btn_ai = styled_button("🤖 Обработать с ИИ", tooltip="Распознать файлы полисов")
        btn_ai.clicked.connect(self._on_process_policies_ai)
        hlayout.addWidget(btn_ai)
        btn_ai_text = styled_button("🤖 Из текста", tooltip="Распознать текст полиса")
        btn_ai_text.clicked.connect(self._on_process_policy_text_ai)
        hlayout.addWidget(btn_ai_text)
        hlayout.addStretch()
        pol_l.addLayout(hlayout)
        pol_view = PolicyTableView(parent=self, deal_id=self.instance.id)
        pol_view.load_data()
        pol_l.addWidget(pol_view)
        self.pol_view = pol_view
        self.policy_tab_idx = self.tabs.addTab(pol_tab, "Полисы")

        # ---------- Платежи ---------------------------------------
        pay_tab = QWidget()
        pay_l = QVBoxLayout(pay_tab)
        btn_pay = styled_button("➕ Платёж", tooltip="Добавить платёж", shortcut="Ctrl+Shift+N")
        btn_pay.clicked.connect(self._on_add_payment)
        self._add_shortcut("Ctrl+Shift+N", self._on_add_payment)
        pay_l.addWidget(btn_pay, alignment=Qt.AlignLeft)
        pay_view = PaymentTableView(parent=self, deal_id=self.instance.id)
        pay_view.load_data()
        pay_l.addWidget(pay_view)
        self.pay_view = pay_view
        self.payment_tab_idx = self.tabs.addTab(pay_tab, "Платежи")

        # ---------- Доходы ---------------------------------------
        income_tab = QWidget()
        income_layout = QVBoxLayout(income_tab)
        btn_income = styled_button("➕ Доход", tooltip="Добавить доход", shortcut="Ctrl+Alt+I")
        btn_income.clicked.connect(self._on_add_income)
        self._add_shortcut("Ctrl+Alt+I", self._on_add_income)
        has_payments = len(get_payments_by_deal_id(self.instance.id)) > 0
        btn_income.setEnabled(has_payments)
        if not has_payments:
            btn_income.setToolTip("Нет доступных платежей для привязки")
        income_layout.addWidget(btn_income, alignment=Qt.AlignLeft)
        income_view = IncomeTableView(parent=self, deal_id=self.instance.id)
        income_view.load_data()
        income_layout.addWidget(income_view)
        self.income_view = income_view
        self.income_tab_idx = self.tabs.addTab(income_tab, "Доходы")

        # ---------- Расходы --------------------------------------
        expense_tab = QWidget()
        expense_layout = QVBoxLayout(expense_tab)
        btn_expense = styled_button("➕ Расход", tooltip="Добавить расход", shortcut="Ctrl+Alt+X")
        btn_expense.clicked.connect(self._on_add_expense)
        self._add_shortcut("Ctrl+Alt+X", self._on_add_expense)
        expense_layout.addWidget(btn_expense, alignment=Qt.AlignLeft)
        expense_view = ExpenseTableView(parent=self, deal_id=self.instance.id)
        expense_view.load_data()
        expense_layout.addWidget(expense_view)
        self.expense_view = expense_view
        self.expense_tab_idx = self.tabs.addTab(expense_tab, "Расходы")

        # ---------- Задачи ---------------------------------------
        task_tab = QWidget()
        vbox = QVBoxLayout(task_tab)
        btn_add_task = styled_button(
            "➕ Задача", tooltip="Добавить задачу", shortcut="Ctrl+Alt+T"
        )
        btn_add_task.clicked.connect(self._on_add_task)
        self._add_shortcut("Ctrl+Alt+T", self._on_add_task)
        vbox.addWidget(btn_add_task, alignment=Qt.AlignLeft)

        task_view = TaskTableView(
            parent=self, deal_id=self.instance.id, autoload=False
        )
        task_view.data_loaded.connect(self._adjust_task_columns)
        vbox.addWidget(task_view)
        task_view.load_data()
        task_view._update_actions_state()
        task_view.table.setSortingEnabled(True)
        task_view.row_double_clicked.connect(self._on_task_double_clicked)
        self.task_view = task_view
        self.task_tab_idx = self.tabs.addTab(task_tab, "Задачи")

    def _adjust_task_columns(self, *_):
        """Настройка колонок таблицы задач во вкладке сделки."""
        tv = getattr(self, "task_view", None)
        if not tv or not tv.model:
            return

        try:
            idx = tv.model.fields.index(Task.title)
        except ValueError:
            idx = -1
        if idx >= 0 and idx != 1:
            tv.model.fields.pop(idx)
            tv.model.fields.insert(1, Task.title)
            tv.model.layoutChanged.emit()

        header = tv.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)

        try:
            idx_title = tv.model.fields.index(Task.title)
            tv.table.setColumnWidth(idx_title, 200)
            tv.table.setColumnHidden(idx_title, False)
        except ValueError:
            pass

        try:
            idx_deal = tv.model.fields.index(Task.deal)
            tv.table.setColumnHidden(idx_deal, True)
        except ValueError:
            pass

        try:
            idx_note = tv.model.fields.index(Task.note)
            tv.table.setColumnWidth(idx_note, 250)
        except ValueError:
            pass
