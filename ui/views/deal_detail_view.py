from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)
from PySide6.QtGui import (
    QSyntaxHighlighter,
    QTextCharFormat,
    QColor,
    QFontDatabase,
    QFont,
)
import re

from database.models import Task
from services.deal_service import (
    get_next_deal,
    get_policies_by_deal_id,
    get_prev_deal,
    get_tasks_by_deal_id,
    update_deal,
)
from services.folder_utils import open_folder, copy_path_to_clipboard
from services.payment_service import get_payments_by_deal_id
from services.policy_service import get_policies_by_deal_id
from ui.common.date_utils import format_date
from ui.common.message_boxes import confirm
from ui.common.styled_widgets import styled_button
from utils.screen_utils import get_scaled_size
from ui.forms.deal_form import DealForm
from ui.forms.import_policy_json_form import ImportPolicyJsonForm
from ui.forms.income_form import IncomeForm
from ui.forms.payment_form import PaymentForm
from ui.forms.policy_form import PolicyForm
from ui.forms.task_form import TaskForm
from ui.views.payment_table_view import PaymentTableView
from ui.views.policy_table_view import PolicyTableView
from ui.views.task_table_view import TaskTableView  # ← наш переиспользуемый вид задач


class _CalcHighlighter(QSyntaxHighlighter):
    """Highlight timestamps at the beginning of each line."""

    _regex = re.compile(r"^\[\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}\]")

    def highlightBlock(self, text: str) -> None:
        m = self._regex.match(text)
        if m:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor("blue"))
            fmt.setFontWeight(QFont.Bold)
            self.setFormat(m.start(), m.end() - m.start(), fmt)


class DealDetailView(QDialog):
    def __init__(self, deal, parent=None):
        super().__init__(parent)
        self.instance = deal
        self.setWindowTitle(
            f"Сделка #{deal.id} — {deal.client.name}: {deal.description}"
        )
        size = get_scaled_size(1200, 800)
        self.resize(size)
        min_w = max(900, int(size.width() * 0.8))
        self.setMinimumSize(min_w, 480)

        self.layout = QVBoxLayout(self)

        # Заголовок
        header = QLabel(f"<h1>Сделка #{deal.id}</h1>")
        header.setTextFormat(Qt.RichText)
        header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.layout.addWidget(header)

        # KPI-панель
        # KPI panel is updated in place to avoid duplicates when refreshed
        self.kpi_layout = QHBoxLayout()
        self.layout.addLayout(self.kpi_layout)
        self._init_kpi_panel()

        # Вкладки
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs, stretch=1)
        self._init_tabs()

        # Быстрые действия
        self._init_actions()

    def _init_kpi_panel(self):
        """(Re)populate the KPI panel without adding new duplicates."""
        # remove previous widgets
        while self.kpi_layout.count():
            item = self.kpi_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        cnt_policies = len(get_policies_by_deal_id(self.instance.id))
        cnt_payments = len(get_payments_by_deal_id(self.instance.id))
        # Здесь используем тот же сервис задач
        cnt_tasks = len(get_tasks_by_deal_id(self.instance.id))

        from services import executor_service as es
        ex = es.get_executor_for_deal(self.instance.id)
        executor_name = ex.full_name if ex else "—"

        for text in [
            f"Полисов: <b>{cnt_policies}</b>",
            f"Платежей: <b>{cnt_payments}</b>",
            f"Задач: <b>{cnt_tasks}</b>",
            f"Исполнитель: <b>{executor_name}</b>",
        ]:
            lbl = QLabel(text)
            lbl.setTextFormat(Qt.RichText)
            self.kpi_layout.addWidget(lbl)
        self.kpi_layout.addStretch()

    def _init_tabs(self):
        # удаляем старые вкладки
        while self.tabs.count():
            w = self.tabs.widget(0)
            self.tabs.removeTab(0)
            w.deleteLater()

        # 1) Информация
        info = QWidget()
        main_layout = QVBoxLayout(info)
        main_layout.setContentsMargins(0, 0, 0, 0)

        info_group = QGroupBox("Основная информация")
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
        form.addRow("Клиент:", tight_label(f"<b>{self.instance.client.name}</b>"))
        form.addRow("Телефон:", tight_label(self.instance.client.phone or "—"))

        start_label = tight_label(format_date(self.instance.start_date))
        form.addRow("Старт:", start_label)

        # Статус — редактируемое текстовое поле
        self.status_edit = QTextEdit(self.instance.status)
        self.status_edit.setFixedHeight(40)
        form.addRow("Статус:", self.status_edit)

        # Описание — только для чтения
        self.desc_edit = QTextEdit(self.instance.description)
        self.desc_edit.setFixedHeight(60)
        self.desc_edit.setReadOnly(True)
        form.addRow("Описание:", self.desc_edit)

        # Напоминание — редактируемая дата
        from ui.common.date_utils import TypableDateEdit

        self.reminder_date = TypableDateEdit(self.instance.reminder_date)
        form.addRow("Напоминание:", self.reminder_date)

        info_group.setLayout(form)
        main_layout.addWidget(info_group)

        # ---- Журнал -------------------------------------------------
        journal_group = QGroupBox("Журнал")
        journal_form = QFormLayout()

        self.calc_append = QTextEdit()
        self.calc_append.setPlaceholderText("Новая запись…")
        self.calc_append.setFixedHeight(50)
        journal_form.addRow("Добавить:", self.calc_append)

        self.calc_view = QTextEdit()
        self.calc_view.setReadOnly(True)
        self.calc_view.setFixedHeight(140)
        self.calc_view.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.calc_view.setPlainText(self.instance.calculations or "—")
        self._calc_highlighter = _CalcHighlighter(self.calc_view.document())
        journal_form.addRow("История:", self.calc_view)

        journal_group.setLayout(journal_form)
        main_layout.addWidget(journal_group)

        self.btn_exec_task = styled_button("📤 Новая задача исполнителю")
        self.btn_exec_task.clicked.connect(self._on_new_exec_task)
        main_layout.addWidget(self.btn_exec_task, alignment=Qt.AlignLeft)

        # ---- Расчёты ------------------------------------------------
        from ui.views.calculation_table_view import CalculationTableView

        calc_group = QGroupBox("Расчёты")
        calc_box = QVBoxLayout()
        btn_calc = styled_button(
            "➕ Запись",
            tooltip="Добавить расчёт",
            shortcut="Ctrl+Shift+A",
        )
        btn_calc.clicked.connect(self._on_add_calculation)
        calc_box.addWidget(btn_calc, alignment=Qt.AlignLeft)
        self.calc_table = CalculationTableView(parent=self, deal_id=self.instance.id)
        calc_box.addWidget(self.calc_table)
        calc_group.setLayout(calc_box)
        main_layout.addWidget(calc_group)

        # Кнопка сохранения
        btn_save = styled_button(
            "💾 Сохранить изменения", shortcut="Ctrl+Enter"
        )
        btn_save.clicked.connect(self._on_inline_save)
        main_layout.addWidget(btn_save, alignment=Qt.AlignRight)

        info.setLayout(main_layout)
        self.tabs.addTab(info, "Информация")

        # 3) Полисы

        pol_tab = QWidget()
        pol_l = QVBoxLayout(pol_tab)

        hlayout = QHBoxLayout()
        btn_pol = styled_button("➕ Полис", tooltip="Добавить полис", shortcut="Ctrl+N")
        btn_pol.clicked.connect(self._on_add_policy)
        hlayout.addWidget(btn_pol)

        btn_import = styled_button(
            "📥 Импорт из JSON", tooltip="Импорт полиса по данным"
        )
        btn_import.clicked.connect(self._on_import_policy_json)
        hlayout.addWidget(btn_import)

        hlayout.addStretch()
        pol_l.addLayout(hlayout)

        pol_view = PolicyTableView(
            parent=self,
            deal_id=self.instance.id,
        )
        pol_view.load_data()
        pol_l.addWidget(pol_view)

        self.tabs.addTab(pol_tab, "Полисы")

        # 3) Платежи
        pay_tab = QWidget()
        pay_l = QVBoxLayout(pay_tab)
        btn_pay = styled_button(
            "➕ Платёж", tooltip="Добавить платёж", shortcut="Ctrl+Shift+N"
        )
        btn_pay.clicked.connect(self._on_add_payment)
        payments = list(get_payments_by_deal_id(self.instance.id))

        pay_view = PaymentTableView(
            parent=self,
            deal_id=self.instance.id,
        )
        pay_view.load_data()
        pay_l.addWidget(pay_view)

        self.tabs.addTab(pay_tab, "Платежи")

        # 4) Доходы
        from ui.views.income_table_view import IncomeTableView

        income_tab = QWidget()
        income_layout = QVBoxLayout(income_tab)

        btn_income = styled_button(
            "➕ Доход",
            tooltip="Добавить доход",
            shortcut="Ctrl+Alt+I",
        )
        btn_income.clicked.connect(self._on_add_income)
        has_payments = len(get_payments_by_deal_id(self.instance.id)) > 0
        btn_income.setEnabled(has_payments)
        if not has_payments:
            btn_income.setToolTip("Нет доступных платежей для привязки")
        income_layout.addWidget(btn_income, alignment=Qt.AlignLeft)

        income_view = IncomeTableView(parent=self, deal_id=self.instance.id)
        income_view.load_data()
        income_layout.addWidget(income_view)

        self.tabs.addTab(income_tab, "Доходы")

        # 5) Расходы
        from ui.views.expense_table_view import ExpenseTableView

        expense_tab = QWidget()
        expense_layout = QVBoxLayout(expense_tab)
        btn_expense = styled_button(
            "➕ Расход",
            tooltip="Добавить расход",
            shortcut="Ctrl+Alt+X",
        )
        btn_expense.clicked.connect(self._on_add_expense)
        expense_layout.addWidget(btn_expense, alignment=Qt.AlignLeft)

        expense_view = ExpenseTableView(parent=self, deal_id=self.instance.id)
        expense_view.load_data()
        expense_layout.addWidget(expense_view)

        self.tabs.addTab(expense_tab, "Расходы")

        # 4) Задачи — внедряем TaskTableView с фильтром по сделке
        # ─── Задачи ───────────────────────────────────────────
        task_tab = QWidget()
        vbox = QVBoxLayout(task_tab)

        btn_add_task = styled_button(
            "➕ Задача",
            tooltip="Добавить задачу",
            shortcut="Ctrl+Alt+T",
        )
        btn_add_task.clicked.connect(self._on_add_task)
        vbox.addWidget(btn_add_task, alignment=Qt.AlignLeft)


        # Подгружаем ТОЛЬКО задачи этой сделки
        from services.task_service import get_tasks_by_deal

        tasks = list(get_tasks_by_deal(self.instance.id))

        task_view = TaskTableView(parent=self, deal_id=self.instance.id)
        task_view.data_loaded.connect(self._adjust_task_columns)
        vbox.addWidget(task_view)
        self.task_view = task_view

        task_view.set_model_class_and_items(Task, tasks, total_count=len(tasks))
        self._adjust_task_columns()
        sel = task_view.table.selectionModel()
        if sel:
            sel.selectionChanged.connect(task_view._update_actions_state)
            task_view._update_actions_state()

        task_view.table.setSortingEnabled(True)
        task_view.row_double_clicked.connect(self._on_task_double_clicked)

        self.tabs.addTab(task_tab, "Задачи")
        self.task_view = task_view  # сохраняем для refresh

    def _adjust_task_columns(self, *_):
        """Настройка колонок таблицы задач во вкладке сделки."""
        tv = getattr(self, "task_view", None)
        if not tv or not tv.model:
            return

        header = tv.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)

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

    def _init_actions(self):
        box = QHBoxLayout()
        box.setSpacing(6)
        box.addStretch()
        btn_edit = styled_button("✏️ Редактировать", shortcut="Ctrl+E")
        btn_edit.clicked.connect(self._on_edit)
        box.addWidget(btn_edit)
        btn_folder = styled_button("📂 Папка", shortcut="Ctrl+O")
        btn_folder.clicked.connect(self._open_folder)
        box.addWidget(btn_folder)
        btn_copy = styled_button(
            "📋",
            tooltip="Скопировать путь к папке",
            shortcut="Ctrl+Shift+C",
        )
        btn_copy.clicked.connect(self._copy_folder_path)
        box.addWidget(btn_copy)

        self.btn_exec = styled_button("👤 Исполнитель", shortcut="Ctrl+Shift+E")
        self.btn_exec.clicked.connect(self._on_toggle_executor)
        box.addWidget(self.btn_exec)
        btn_wa = styled_button("💬 WhatsApp", shortcut="Ctrl+Shift+W")
        btn_wa.clicked.connect(self._open_whatsapp)
        box.addWidget(btn_wa)
        btn_prev = styled_button("◀ Назад", shortcut="Alt+Left")
        btn_prev.clicked.connect(self._on_prev_deal)
        box.addWidget(btn_prev)
        btn_next = styled_button("▶ Далее", shortcut="Alt+Right")
        btn_next.clicked.connect(self._on_next_deal)
        box.addWidget(btn_next)
        self.layout.addLayout(box)
        if not self.instance.is_closed:
            btn_close = styled_button("🔒 Закрыть сделку", shortcut="Ctrl+Shift+L")
            btn_close.clicked.connect(self._on_close_deal)
            box.addWidget(btn_close)

        self._update_exec_button()

    def _on_edit(self):
        form = DealForm(self.instance, parent=self)
        if form.exec():
            self._init_kpi_panel()
            self._init_tabs()

    def _on_add_policy(self):
        """
        Добавить новый полис к ТЕКУЩЕЙ сделке:
        – клиент и сделка подставляются автоматически,
        клиент изменить нельзя, сделку не показываем.
        """
        form = PolicyForm(
            parent=self,
            forced_client=self.instance.client,
            forced_deal=self.instance,
        )
        if form.exec():
            self._init_tabs()  # перерисовать KPI + таблицы

    def _on_add_payment(self):
        form = PaymentForm(parent=self)
        if form.exec():
            self._init_tabs()

    def _on_add_task(self):
        form = TaskForm(parent=self, forced_deal=self.instance)
        # префилл по сделке
        if hasattr(form, "deal_combo"):
            idx = form.deal_combo.findData(self.instance.id)
            if idx >= 0:
                form.deal_combo.setCurrentIndex(idx)
        if form.exec():
            self.task_view.refresh()  # загрузит только задачи сделки
            self._init_kpi_panel()

    def _on_new_exec_task(self):
        form = TaskForm(parent=self, forced_deal=self.instance)
        if hasattr(form, "deal_combo"):
            idx = form.deal_combo.findData(self.instance.id)
            if idx >= 0:
                form.deal_combo.setCurrentIndex(idx)
        if form.exec():
            task = getattr(form, "saved_instance", None)
            if not task:
                return
            from services import executor_service as es
            ex = es.get_executor_for_deal(self.instance.id)
            if not ex:
                from ui.common.message_boxes import show_error
                show_error("Исполнитель не привязан")
            else:
                from services.task_service import queue_task
                queue_task(task.id)
            if hasattr(self, "task_view"):
                self.task_view.refresh()
            self._init_kpi_panel()

    def _open_folder(self):
        open_folder(
            self.instance.drive_folder_path or self.instance.drive_folder_link,
            parent=self,  # QWidget, чтобы показывались QMessageBox-ы
        )

    def _copy_folder_path(self):
        copy_path_to_clipboard(
            self.instance.drive_folder_path or self.instance.drive_folder_link,
            parent=self,
        )

    def _on_toggle_executor(self):
        from services import executor_service as es
        current = es.get_executor_for_deal(self.instance.id)
        if current:
            if confirm("Отвязать исполнителя?"):
                es.unassign_executor(self.instance.id)
                self._update_exec_button()
                self._init_kpi_panel()
            return

        executors = list(es.get_available_executors())
        items = [f"{ex.full_name} ({ex.tg_id})" for ex in executors]
        from PySide6.QtWidgets import QInputDialog

        choice, ok = QInputDialog.getItem(
            self, "Выбор исполнителя", "Исполнитель:", items, 0, False
        )
        if ok and choice:
            import re

            m = re.search(r"(\d+)", choice)
            if m:
                tg_id = int(m.group(1))
                es.assign_executor(self.instance.id, tg_id)
            self._update_exec_button()
            self._init_kpi_panel()

    def _update_exec_button(self):
        from services import executor_service as es
        ex = es.get_executor_for_deal(self.instance.id)
        if ex:
            self.btn_exec.setText(f"Отвязать {ex.full_name}")
        else:
            self.btn_exec.setText("Привязать исполнителя")

    def _open_whatsapp(self):
        from services.client_service import format_phone_for_whatsapp, open_whatsapp

        phone = self.instance.client.phone
        if phone:
            open_whatsapp(format_phone_for_whatsapp(phone))

    def _on_inline_save(self):
        from services.deal_service import update_deal

        status = self.status_edit.toPlainText().strip()
        reminder = (
            self.reminder_date.date().toPython()
            if self.reminder_date.date().isValid()
            else None
        )
        new_calc_part = self.calc_append.toPlainText().strip()
        if reminder:
            delta = abs(reminder - date.today())
            if delta > timedelta(days=31):
                if not confirm(
                    f"Дата напоминания отличается от текущей более чем на месяц.\nУстановить {reminder:%d.%m.%Y}?"
                ):
                    return

        try:
            update_deal(
                self.instance,
                status=status or None,
                reminder_date=reminder,
                journal_entry=new_calc_part or None,
            )
            self.calc_append.clear()
            self.calc_view.setPlainText(self.instance.calculations or "—")
            if new_calc_part:
                self.calc_table.refresh()
        except Exception as e:
            from ui.common.message_boxes import show_error

            show_error(str(e))

    def _on_task_double_clicked(self, task):
        form = TaskForm(task, parent=self)
        if form.exec():
            self.task_view.refresh()
            self._init_kpi_panel()

    def _on_add_calculation(self):
        from ui.forms.calculation_form import CalculationForm

        form = CalculationForm(parent=self, deal_id=self.instance.id)
        if form.exec():
            self.calc_table.refresh()

    def _on_add_income(self):
        dlg = IncomeForm(parent=self, deal_id=self.instance.id)
        if dlg.exec():
            self._init_tabs()  # перезапустить вкладки для обновления данных

    def _on_prev_deal(self):
        prev = get_prev_deal(self.instance)
        if prev:
            self.close()
            DealDetailView(prev).exec()

    def _on_next_deal(self):
        next_ = get_next_deal(self.instance)
        if next_:
            self.close()
            DealDetailView(next_).exec()

    def _on_add_expense(self):
        from ui.forms.expense_form import ExpenseForm

        dlg = ExpenseForm(parent=self, deal_id=self.instance.id)
        if dlg.exec():
            self._init_tabs()  # чтобы обновить таблицу расходов

    def _on_close_deal(self):
        dlg = CloseDealDialog(self)
        if dlg.exec() == QDialog.Accepted:
            reason = dlg.get_reason()
            if not reason:
                from ui.common.message_boxes import show_error

                show_error("Причина обязательна.")
                return
            update_deal(self.instance, is_closed=True, closed_reason=reason)
            from ui.common.message_boxes import show_info

            show_info("Сделка успешно закрыта.")
            self.close()
            DealDetailView(self.instance).exec()

    def _on_import_policy_json(self):
        dlg = ImportPolicyJsonForm(
            parent=self,
            forced_client=self.instance.client,
            forced_deal=self.instance,
        )
        if dlg.exec():
            self._init_tabs()


class CloseDealDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Закрытие сделки")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Укажите причину закрытия:"))
        self.reason_edit = QTextEdit()
        layout.addWidget(self.reason_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_reason(self):
        return self.reason_edit.toPlainText().strip()
