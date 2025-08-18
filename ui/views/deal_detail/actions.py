import base64
import logging
import os
import re
from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QHBoxLayout, QInputDialog

from database.models import Deal
from services.deal_service import (
    get_deal_by_id,
    get_next_deal,
    get_prev_deal,
    update_deal,
)
from services.folder_utils import (
    copy_path_to_clipboard,
    move_file_to_folder,
    open_folder,
)
from services.payment_service import get_payments_by_deal_id
from services.policy_service import get_policies_by_deal_id
from ui import settings as ui_settings
from ui.common.message_boxes import confirm, show_error, show_info
from ui.common.styled_widgets import styled_button
from ui.forms.client_form import ClientForm
from ui.forms.deal_form import DealForm
from ui.forms.import_policy_json_form import ImportPolicyJsonForm
from ui.forms.income_form import IncomeForm
from ui.forms.payment_form import PaymentForm
from ui.forms.policy_form import PolicyForm
from ui.forms.task_form import TaskForm

from .dialogs import CloseDealDialog
from .widgets import _with_day_separators

logger = logging.getLogger(__name__)


class DealActionsMixin:
    def _init_actions(self):
        box = QHBoxLayout()
        box.setSpacing(6)
        box.addStretch()
        btn_edit = styled_button("✏️ Редактировать", shortcut="Ctrl+E")
        btn_edit.clicked.connect(self._on_edit)
        self._add_shortcut("Ctrl+E", self._on_edit)
        box.addWidget(btn_edit)
        btn_edit_client = styled_button(
            "📝 Клиент", tooltip="Редактировать клиента", shortcut="Ctrl+Shift+K"
        )
        btn_edit_client.clicked.connect(self._on_edit_client)
        self._add_shortcut("Ctrl+Shift+K", self._on_edit_client)
        box.addWidget(btn_edit_client)
        btn_folder = styled_button("📂 Папка", shortcut="Ctrl+O")
        btn_folder.clicked.connect(self._open_folder)
        self._add_shortcut("Ctrl+O", self._open_folder)
        box.addWidget(btn_folder)
        btn_copy = styled_button(
            "📋",
            tooltip="Скопировать путь к папке",
            shortcut="Ctrl+Shift+C",
        )
        btn_copy.clicked.connect(self._copy_folder_path)
        self._add_shortcut("Ctrl+Shift+C", self._copy_folder_path)
        box.addWidget(btn_copy)

        self.btn_exec = styled_button("👤 Исполнитель", shortcut="Ctrl+Shift+E")
        self.btn_exec.clicked.connect(self._on_toggle_executor)
        self._add_shortcut("Ctrl+Shift+E", self._on_toggle_executor)
        box.addWidget(self.btn_exec)
        btn_wa = styled_button("💬 WhatsApp", shortcut="Ctrl+Shift+W")
        btn_wa.clicked.connect(self._open_whatsapp)
        self._add_shortcut("Ctrl+Shift+W", self._open_whatsapp)
        box.addWidget(btn_wa)
        btn_prev = styled_button("◀ Назад", shortcut="Alt+Left")
        btn_prev.clicked.connect(self._on_prev_deal)
        self._add_shortcut("Alt+Left", self._on_prev_deal)
        box.addWidget(btn_prev)
        btn_next = styled_button("▶ Далее", shortcut="Alt+Right")
        btn_next.clicked.connect(self._on_next_deal)
        self._add_shortcut("Alt+Right", self._on_next_deal)
        box.addWidget(btn_next)

        has_prev = get_prev_deal(self.instance)
        has_next = get_next_deal(self.instance)
        btn_prev.setEnabled(has_prev is not None)
        btn_next.setEnabled(has_next is not None)
        self.btn_prev = btn_prev
        self.btn_next = btn_next

        if not self.instance.is_closed:
            btn_delay = styled_button("⏳ Отложить", shortcut="Ctrl+Shift+N")
            btn_delay.clicked.connect(self._on_delay_to_event)
            self._add_shortcut("Ctrl+Shift+N", self._on_delay_to_event)
            box.addWidget(btn_delay)
        self.layout.addLayout(box)
        if not self.instance.is_closed:
            btn_close = styled_button("🔒 Закрыть сделку", shortcut="Ctrl+Shift+L")
            btn_close.clicked.connect(self._on_close_deal)
            self._add_shortcut("Ctrl+Shift+L", self._on_close_deal)
            box.addWidget(btn_close)

        self._update_exec_button()

    def _add_shortcut(self, seq: str, callback):
        sc = QShortcut(QKeySequence(seq), self)
        sc.setContext(Qt.WidgetWithChildrenShortcut)
        sc.activated.connect(callback)
        self._shortcuts.append(sc)

    def _register_shortcuts(self):
        """Enable hotkeys for saving with closing and refreshing."""
        self._add_shortcut("Ctrl+Shift+Enter", self._on_save_and_close)
        self._add_shortcut("F5", self._on_refresh)

    def _load_settings(self):
        """Восстанавливает сохранённые параметры окна."""
        st = ui_settings.get_window_settings(self.SETTINGS_KEY)
        geom = st.get("geometry")
        if geom:
            try:
                self.restoreGeometry(base64.b64decode(geom))
            except Exception:
                pass
        idx = st.get("tab_index")
        if idx is not None and 0 <= int(idx) < self.tabs.count():
            self.tabs.setCurrentIndex(int(idx))

    def _save_settings(self):
        """Сохраняет текущие параметры окна."""
        st = {
            "geometry": base64.b64encode(self.saveGeometry()).decode("ascii"),
            "tab_index": self.tabs.currentIndex(),
        }
        ui_settings.set_window_settings(self.SETTINGS_KEY, st)

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)

    def _on_edit(self):
        form = DealForm(self.instance, parent=self)
        if form.exec():
            self._init_kpi_panel()
            self._init_tabs()

    def _on_edit_client(self):
        form = ClientForm(self.instance.client, parent=self)
        if form.exec():
            self.instance.client = form.instance
            self.setWindowTitle(
                f"Сделка #{self.instance.id} — {self.instance.client.name}: {self.instance.description}"
            )
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
            self._init_kpi_panel()
            self._init_tabs()  # перерисовать KPI + таблицы

    def _on_add_payment(self):
        form = PaymentForm(parent=self)
        if form.exec():
            self._init_kpi_panel()
            self._init_tabs()

    def _on_add_task(self):
        form = TaskForm(parent=self, forced_deal=self.instance)
        if hasattr(form, "deal_combo"):
            idx = form.deal_combo.findData(self.instance.id)
            if idx >= 0:
                form.deal_combo.setCurrentIndex(idx)
        if form.exec():
            self._init_kpi_panel()
            self._init_tabs()

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
            from services.task_service import queue_task
            ex = es.get_executor_for_deal(self.instance.id)
            if not ex:
                from ui.common.message_boxes import show_error

                show_error("Исполнитель не привязан")
            else:
                queue_task(task.id)
            self._init_kpi_panel()
            self._init_tabs()

    def _open_folder(self):
        path = self.instance.drive_folder_path or self.instance.drive_folder_link
        if self.instance.drive_folder_path and not os.path.isdir(
            self.instance.drive_folder_path
        ):
            from ui.common.message_boxes import confirm
            from services.folder_utils import create_deal_folder

            if confirm("Папка не найдена. Создать новую?"):
                new_path, link = create_deal_folder(
                    self.instance.client.name,
                    self.instance.description,
                    client_drive_link=self.instance.client.drive_folder_link,
                )
                self.instance.drive_folder_path = new_path
                self.instance.drive_folder_link = link
                self.instance.save(
                    only=[Deal.drive_folder_path, Deal.drive_folder_link]
                )
                path = new_path or link
            else:
                return

        open_folder(path, parent=self)

    def _copy_folder_path(self):
        copy_path_to_clipboard(
            self.instance.drive_folder_path or self.instance.drive_folder_link,
            parent=self,
        )

    def _ensure_local_folder(self) -> str | None:
        """Ensure local deal folder exists and return its path."""
        path = self.instance.drive_folder_path
        if path and os.path.isdir(path):
            return path

        from services.folder_utils import create_deal_folder
        from ui.common.message_boxes import confirm

        if confirm("Папка не найдена. Создать новую?"):
            new_path, link = create_deal_folder(
                self.instance.client.name,
                self.instance.description,
                client_drive_link=self.instance.client.drive_folder_link,
            )
            self.instance.drive_folder_path = new_path
            self.instance.drive_folder_link = link
            self.instance.save(only=[Deal.drive_folder_path, Deal.drive_folder_link])
            return new_path

        return None

    def _handle_dropped_files(self, files: list[str]) -> None:
        """Move dropped files into the deal folder."""
        dest = self._ensure_local_folder()
        if not dest:
            return
        for src in files:
            move_file_to_folder(src, dest)

    def dragEnterEvent(self, event):  # noqa: D401 - Qt override
        """Qt drag enter handler."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._orig_style = self.styleSheet()
            self.setStyleSheet(
                self._orig_style + "; border: 2px dashed #4CAF50;"
                if self._orig_style
                else "border: 2px dashed #4CAF50;"
            )

    def dragLeaveEvent(self, event):  # noqa: D401 - Qt override
        """Qt drag leave handler."""
        if hasattr(self, "_orig_style"):
            self.setStyleSheet(self._orig_style)
        event.accept()

    def dropEvent(self, event):  # noqa: D401 - Qt override
        """Qt drop handler."""
        urls = [u for u in event.mimeData().urls() if u.isLocalFile()]
        if urls:
            files = [u.toLocalFile() for u in urls]
            self._handle_dropped_files(files)
            show_info(f"Добавлено файлов: {len(files)}")
            event.acceptProposedAction()
        if hasattr(self, "_orig_style"):
            self.setStyleSheet(self._orig_style)

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
        choice, ok = QInputDialog.getItem(
            self, "Выбор исполнителя", "Исполнитель:", items, 0, False
        )
        if ok and choice:
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

    def _update_nav_buttons(self):
        self.btn_prev.setEnabled(get_prev_deal(self.instance) is not None)
        self.btn_next.setEnabled(get_next_deal(self.instance) is not None)

    def _open_whatsapp(self):
        from services.client_service import (
            format_phone_for_whatsapp,
            open_whatsapp,
        )

        phone = self.instance.client.phone
        if phone:
            open_whatsapp(format_phone_for_whatsapp(phone))

    def _on_inline_save(self):
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
            self.calc_view.setPlainText(
                _with_day_separators(self.instance.calculations)
            )
            if new_calc_part:
                self.calc_table.refresh()
        except Exception as e:
            show_error(str(e))

    def _on_save_and_close(self):
        self._on_inline_save()
        self.accept()

    def _on_refresh(self):
        try:
            from services.sheets_service import sync_calculations_from_sheet

            added = sync_calculations_from_sheet()
            if added:
                show_info(f"Добавлено расчётов: {added}")
        except Exception as e:  # noqa: BLE001
            logger.exception("Sheets sync failed")
            show_error(str(e))

        fresh = get_deal_by_id(self.instance.id)
        if fresh:
            self.instance = fresh
            self.setWindowTitle(
                f"Сделка #{fresh.id} — {fresh.client.name}: {fresh.description}"
            )
            self._init_kpi_panel()
            self._init_tabs()
            self._update_nav_buttons()

    def _on_task_double_clicked(self, task):
        form = TaskForm(task, parent=self)
        if form.exec():
            self._init_kpi_panel()
            self._init_tabs()

    def _on_add_calculation(self):
        from ui.forms.calculation_form import CalculationForm

        form = CalculationForm(parent=self, deal_id=self.instance.id)
        if form.exec():
            self.calc_table.refresh()

    def _on_add_income(self):
        dlg = IncomeForm(parent=self, deal_id=self.instance.id)
        if dlg.exec():
            self._init_kpi_panel()
            self._init_tabs()

    def _on_prev_deal(self):
        prev = get_prev_deal(self.instance)
        if prev:
            from .view import DealDetailView

            self.close()
            DealDetailView(prev).exec()

    def _on_next_deal(self):
        next_ = get_next_deal(self.instance)
        if next_:
            from .view import DealDetailView

            self.close()
            DealDetailView(next_).exec()

    def _on_add_expense(self):
        from ui.forms.expense_form import ExpenseForm

        dlg = ExpenseForm(parent=self, deal_id=self.instance.id)
        if dlg.exec():
            self._init_kpi_panel()
            self._init_tabs()

    def _on_close_deal(self):
        dlg = CloseDealDialog(self)
        if dlg.exec() == QDialog.Accepted:
            reason = dlg.get_reason()
            if not reason:
                show_error("Причина обязательна.")
                return
            update_deal(self.instance, is_closed=True, closed_reason=reason)
            show_info("Сделка успешно закрыта.")
            from .view import DealDetailView

            self.close()
            DealDetailView(self.instance).exec()

    def _on_import_policy_json(self):
        dlg = ImportPolicyJsonForm(
            parent=self,
            forced_client=self.instance.client,
            forced_deal=self.instance,
        )
        if dlg.exec():
            self._init_kpi_panel()
            self._init_tabs()

    def _on_process_policies_ai(self):
        from ui.forms.ai_policy_files_dialog import AiPolicyFilesDialog

        dlg = AiPolicyFilesDialog(
            parent=self,
            forced_client=self.instance.client,
            forced_deal=self.instance,
        )
        if dlg.exec():
            self._init_kpi_panel()
            self._init_tabs()

    def _on_process_policy_text_ai(self):
        from ui.forms.ai_policy_text_dialog import AiPolicyTextDialog

        dlg = AiPolicyTextDialog(
            parent=self,
            forced_client=self.instance.client,
            forced_deal=self.instance,
        )
        if dlg.exec():
            self._init_kpi_panel()
            self._init_tabs()

    def _on_delay_to_event(self):
        events = self._collect_upcoming_events()
        if not events:
            show_info("Будущих событий не найдено")
            return

        from ui.forms.deal_next_event_dialog import DealNextEventDialog

        dlg = DealNextEventDialog(events, parent=self)
        if dlg.exec():
            reminder = dlg.get_reminder_date()
            update_deal(self.instance, reminder_date=reminder, status=str(reminder.year))
            self.accept()

    def _collect_upcoming_events(self) -> list[tuple[str, date]]:
        today = date.today()
        events: list[tuple[str, date]] = []

        for p in get_payments_by_deal_id(self.instance.id):
            if p.actual_payment_date is None and p.payment_date >= today:
                label = f"Платёж {p.payment_date:%d.%m.%Y}"
                events.append((label, p.payment_date))

        for pol in get_policies_by_deal_id(self.instance.id):
            if pol.end_date and pol.end_date >= today:
                events.append((f"Окончание полиса {pol.policy_number}", pol.end_date))

        events.sort(key=lambda e: e[1])
        return events
