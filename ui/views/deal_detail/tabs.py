from datetime import date, timedelta

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QLabel,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QScrollArea,
    QSizePolicy,
    QLineEdit,
    QCompleter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from database.models import Task
from services.deal_service import get_distinct_statuses
from services import deal_journal
from ui.common.date_utils import TypableDateEdit, format_date
from ui.common.styled_widgets import styled_button
from ..calculation_table_view import CalculationTableView
from ..expense_table_view import ExpenseTableView
from ..income_table_view import IncomeTableView
from ..payment_table_view import PaymentTableView
from ..policy_table_view import PolicyTableView
from ..task_table_view import TaskTableView
from .widgets import CollapsibleWidget
from .sticky_notes import StickyNotesBoard


class DealTabsMixin:
    @staticmethod
    def _mark_flow_button(button):
        button.setProperty("flow_fill_row", False)
        return button

    def _create_info_panel(self) -> CollapsibleWidget:
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
            lbl.setWordWrap(True)
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            return lbl

        self.id_label = tight_label("")
        form.addRow("ID:", self.id_label)

        self.client_label = tight_label("")
        form.addRow("Клиент:", self.client_label)

        self.phone_label = tight_label("")
        form.addRow("Телефон:", self.phone_label)

        self.start_label = tight_label("")
        form.addRow("Старт:", self.start_label)

        self.status_edit = QLineEdit()
        status_completer = QCompleter(get_distinct_statuses())
        self.status_edit.setCompleter(status_completer)
        form.addRow("Статус:", self.status_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setMinimumHeight(60)
        self.desc_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.desc_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.desc_edit.setReadOnly(True)
        form.addRow("Описание:", self.desc_edit)

        self.reminder_date = TypableDateEdit(self.instance.reminder_date)
        reminder_row = QWidget()
        reminder_layout = QHBoxLayout(reminder_row)
        reminder_layout.setContentsMargins(0, 0, 0, 0)
        reminder_layout.addWidget(self.reminder_date)
        for text, days in [
            ("Завтра", 1),
            ("+2 дня", 2),
            ("+3 дня", 3),
            ("+5 дней", 5),
        ]:
            btn = self._mark_flow_button(styled_button(text))
            btn.clicked.connect(lambda _, d=days: self._postpone_reminder(d))
            reminder_layout.addWidget(btn)
        form.addRow("Напоминание:", reminder_row)

        info_panel.setContentLayout(form)
        self.info_panel = info_panel
        self._refresh_info_panel()
        return info_panel

    def _refresh_info_panel(self) -> None:
        if not hasattr(self, "status_edit"):
            return

        self.id_label.setText(str(self.instance.id))

        client_html = f"<b>{self.instance.client.name}</b>"
        note = self.instance.client.note
        if note:
            client_html += f" <span style='color:red'>{note}</span>"
        self.client_label.setText(client_html)

        self.phone_label.setText(self.instance.client.phone or "—")
        self.start_label.setText(format_date(self.instance.start_date))

        self.status_edit.setText(self.instance.status or "")

        description = self.instance.description or ""
        self.desc_edit.setPlainText(description)

        reminder = getattr(self.instance, "reminder_date", None)
        if reminder:
            qdate = QDate(reminder.year, reminder.month, reminder.day)
            self.reminder_date.setDate(qdate)
        else:
            self.reminder_date.clear()

    def _init_tabs(self):
        self._refresh_info_panel()
        current = self.tabs.currentIndex()
        # удаляем старые вкладки
        while self.tabs.count():
            w = self.tabs.widget(0)
            self.tabs.removeTab(0)
            w.deleteLater()

        if hasattr(self, "_tab_action_factories"):
            self._tab_action_factories.clear()
        if hasattr(self, "_rebuild_tab_actions"):
            self._rebuild_tab_actions()

        # ---------- Главная вкладка ---------------------------------
        deal_tab = QWidget()
        deal_layout = QVBoxLayout(deal_tab)
        deal_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        journal_panel = CollapsibleWidget("Журнал")
        journal_form = QFormLayout()

        self.calc_append = QTextEdit()
        self.calc_append.setPlaceholderText("Новая запись…")
        self.calc_append.setFixedHeight(50)

        calc_append_container = QWidget()
        calc_append_layout = QVBoxLayout(calc_append_container)
        calc_append_layout.setContentsMargins(0, 0, 0, 0)
        calc_append_layout.setSpacing(4)
        calc_append_layout.addWidget(self.calc_append)

        self.btn_add_note = self._mark_flow_button(
            styled_button("💾 Добавить заметку")
        )
        self.btn_add_note.clicked.connect(self._on_add_note)
        calc_append_layout.addWidget(self.btn_add_note, alignment=Qt.AlignLeft)

        journal_form.addRow("Добавить:", calc_append_container)

        self.notes_board = StickyNotesBoard()
        self.notes_board.archive_requested.connect(self._on_archive_note)
        self.notes_board.restore_requested.connect(self._on_restore_note)
        active_entries, archived_entries = deal_journal.load_entries(self.instance)
        self.notes_board.set_entries(active_entries, archived_entries)
        journal_form.addRow("Заметки:", self.notes_board)

        self.btn_exec_task = self._mark_flow_button(
            styled_button("📤 Новая задача исполнителю")
        )
        self.btn_exec_task.clicked.connect(self._on_new_exec_task)

        j_layout = QVBoxLayout()
        j_layout.addLayout(journal_form)
        j_layout.addWidget(self.btn_exec_task, alignment=Qt.AlignLeft)
        journal_panel.setContentLayout(j_layout)
        container_layout.addWidget(journal_panel)

        calc_panel = CollapsibleWidget("Расчёты")
        calc_layout = QVBoxLayout()
        btn_calc = self._mark_flow_button(
            styled_button("➕ Запись", tooltip="Добавить расчёт", shortcut="Ctrl+Shift+A")
        )
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

        btn_save = self._mark_flow_button(
            styled_button("💾 Сохранить изменения", shortcut="Ctrl+Enter")
        )
        btn_save.clicked.connect(self._on_inline_save)
        self._add_shortcut("Ctrl+Enter", self._on_inline_save)
        btn_save_close = self._mark_flow_button(
            styled_button(
                "💾 Сохранить и закрыть", shortcut="Ctrl+Shift+Enter"
            )
        )
        btn_save_close.clicked.connect(self._on_save_and_close)
        btn_refresh = self._mark_flow_button(
            styled_button("🔄 Обновить", shortcut="F5")
        )
        btn_refresh.clicked.connect(self._on_refresh)

        self.deal_tab_idx = self.tabs.addTab(deal_tab, "Сделка")
        self.register_tab_actions(
            self.deal_tab_idx, [btn_save, btn_save_close, btn_refresh]
        )

        # ---------- Полисы -----------------------------------------
        pol_tab = QWidget()
        pol_l = QVBoxLayout(pol_tab)
        btn_pol = self._mark_flow_button(
            styled_button("➕ Полис", tooltip="Добавить полис", shortcut="Ctrl+N")
        )
        btn_pol.clicked.connect(self._on_add_policy)
        self._add_shortcut("Ctrl+N", self._on_add_policy)
        btn_import = self._mark_flow_button(
            styled_button("📥 Импорт из JSON", tooltip="Импорт полиса по данным")
        )
        btn_import.clicked.connect(self._on_import_policy_json)
        btn_ai = self._mark_flow_button(
            styled_button("🤖 Обработать с ИИ", tooltip="Распознать файлы полисов")
        )
        btn_ai.clicked.connect(self._on_process_policies_ai)
        btn_ai_text = self._mark_flow_button(
            styled_button("🤖 Из текста", tooltip="Распознать текст полиса")
        )
        btn_ai_text.clicked.connect(self._on_process_policy_text_ai)
        pol_view = PolicyTableView(parent=self, deal_id=self.instance.id)
        pol_view.load_data()
        pol_l.addWidget(pol_view)
        self.pol_view = pol_view
        pol_open = getattr(self, "cnt_policies_open", 0)
        pol_closed = getattr(self, "cnt_policies_closed", 0)
        self.policy_tab_idx = self.tabs.addTab(
            pol_tab, f"Полисы {pol_open} ({pol_closed})"
        )
        self.register_tab_actions(
            self.policy_tab_idx,
            [btn_pol, btn_import, btn_ai, btn_ai_text],
        )

        # ---------- Платежи ---------------------------------------
        pay_tab = QWidget()
        pay_l = QVBoxLayout(pay_tab)
        btn_pay = self._mark_flow_button(
            styled_button("➕ Платёж", tooltip="Добавить платёж", shortcut="Ctrl+Shift+P")
        )
        btn_pay.clicked.connect(self._on_add_payment)
        self._add_shortcut("Ctrl+Shift+P", self._on_add_payment)
        pay_view = PaymentTableView(
            parent=self, deal_id=self.instance.id, can_restore=False
        )
        pay_view.load_data()
        pay_l.addWidget(pay_view)
        self.pay_view = pay_view
        pay_open = getattr(self, "cnt_payments_open", 0)
        pay_closed = getattr(self, "cnt_payments_closed", 0)
        self.payment_tab_idx = self.tabs.addTab(
            pay_tab, f"Платежи {pay_open} ({pay_closed})"
        )
        self.register_tab_actions(self.payment_tab_idx, [btn_pay])

        # ---------- Доходы ---------------------------------------
        income_tab = QWidget()
        income_layout = QVBoxLayout(income_tab)
        btn_income = self._mark_flow_button(
            styled_button("➕ Доход", tooltip="Добавить доход", shortcut="Ctrl+Alt+I")
        )
        btn_income.clicked.connect(self._on_add_income)
        self._add_shortcut("Ctrl+Alt+I", self._on_add_income)
        has_payments = (
            getattr(self, "cnt_payments_open", 0)
            + getattr(self, "cnt_payments_closed", 0)
        ) > 0
        btn_income.setEnabled(has_payments)
        if not has_payments:
            btn_income.setToolTip("Нет доступных платежей для привязки")
        income_view = IncomeTableView(parent=self, deal_id=self.instance.id)
        income_view.load_data()
        income_layout.addWidget(income_view)
        self.income_view = income_view
        inc_open = getattr(self, "cnt_income_open", 0)
        inc_closed = getattr(self, "cnt_income_closed", 0)
        self.income_tab_idx = self.tabs.addTab(
            income_tab, f"Доходы {inc_open} ({inc_closed})"
        )
        self.register_tab_actions(self.income_tab_idx, [btn_income])

        # ---------- Расходы --------------------------------------
        expense_tab = QWidget()
        expense_layout = QVBoxLayout(expense_tab)
        btn_expense = self._mark_flow_button(
            styled_button("➕ Расход", tooltip="Добавить расход", shortcut="Ctrl+Alt+X")
        )
        btn_expense.clicked.connect(self._on_add_expense)
        self._add_shortcut("Ctrl+Alt+X", self._on_add_expense)
        expense_view = ExpenseTableView(parent=self, deal_id=self.instance.id)
        expense_view.load_data()
        expense_layout.addWidget(expense_view)
        self.expense_view = expense_view
        exp_open = getattr(self, "cnt_expense_open", 0)
        exp_closed = getattr(self, "cnt_expense_closed", 0)
        self.expense_tab_idx = self.tabs.addTab(
            expense_tab, f"Расходы {exp_open} ({exp_closed})"
        )
        self.register_tab_actions(self.expense_tab_idx, [btn_expense])

        # ---------- Задачи ---------------------------------------
        task_tab = QWidget()
        vbox = QVBoxLayout(task_tab)
        btn_add_task = self._mark_flow_button(
            styled_button(
                "➕ Задача", tooltip="Добавить задачу", shortcut="Ctrl+Alt+T"
            )
        )
        btn_add_task.clicked.connect(self._on_add_task)
        self._add_shortcut("Ctrl+Alt+T", self._on_add_task)

        task_view = TaskTableView(
            parent=self,
            deal_id=self.instance.id,
            autoload=False,
            resizable_columns=False,
        )
        task_view.data_loaded.connect(self._adjust_task_columns)
        vbox.addWidget(task_view)
        task_view.load_data()
        task_view._update_actions_state()
        task_view.table.setSortingEnabled(True)
        task_view.row_double_clicked.connect(self._on_task_double_clicked)
        self.task_view = task_view
        task_open = getattr(self, "cnt_tasks_open", 0)
        task_closed = getattr(self, "cnt_tasks_closed", 0)
        self.task_tab_idx = self.tabs.addTab(
            task_tab, f"Задачи {task_open} ({task_closed})"
        )
        self.register_tab_actions(self.task_tab_idx, [btn_add_task])

        self.tabs.setCurrentIndex(min(current, self.tabs.count() - 1))
        if hasattr(self, "_rebuild_tab_actions"):
            self._rebuild_tab_actions(self.tabs.currentIndex())

    def _on_archive_note(self, entry_id: str) -> None:
        archived = deal_journal.archive_entry(self.instance, entry_id)
        if archived:
            self.notes_board.load_entries(self.instance)

    def _on_restore_note(self, entry_id: str) -> None:
        restored = deal_journal.restore_entry(self.instance, entry_id)
        if restored:
            self.notes_board.load_entries(self.instance)

    def _postpone_reminder(self, days: int) -> None:
        """Set reminder to today + ``days`` and save/close."""
        new_date = date.today() + timedelta(days=days)
        self.reminder_date.setDate(QDate(new_date.year, new_date.month, new_date.day))
        self._on_save_and_close()

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

        try:
            idx_sent = tv.model.fields.index(Task.queued_at)
            tv.table.setColumnWidth(idx_sent, 150)
        except ValueError:
            pass
