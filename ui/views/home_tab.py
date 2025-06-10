from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtCore import Qt

from services.dashboard_service import (
    get_basic_stats,
    count_sent_tasks,
    count_working_tasks,
    count_unconfirmed_tasks,
    get_upcoming_tasks,
    get_expiring_policies,
    get_upcoming_deal_reminders,
)

from ui.views.task_detail_view import TaskDetailView
from ui.views.policy_detail_view import PolicyDetailView
from ui.views.deal_detail_view import DealDetailView


class HomeTab(QWidget):
    """Стартовая страница со сводной информацией."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("<h2>Добро пожаловать в CRM</h2>")
        layout.addWidget(title)

        self.info_label = QLabel()
        self.info_label.setTextFormat(Qt.RichText)
        layout.addWidget(self.info_label)

        self.tg_tasks_label = QLabel()
        self.tg_tasks_label.setTextFormat(Qt.RichText)
        layout.addWidget(self.tg_tasks_label)

        self.upcoming_tasks_label = QLabel("<b>Ближайшие 10 задач</b>")
        self.upcoming_tasks_label.setTextFormat(Qt.RichText)
        layout.addWidget(self.upcoming_tasks_label)
        self.upcoming_tasks_list = QListWidget()
        layout.addWidget(self.upcoming_tasks_list)
        self.upcoming_tasks_list.itemDoubleClicked.connect(self.open_task_detail)

        self.expiring_policies_label = QLabel(
            "<b>Ближайшие 10 заканчивающихся полисов</b>"
        )
        self.expiring_policies_label.setTextFormat(Qt.RichText)
        layout.addWidget(self.expiring_policies_label)
        self.expiring_policies_list = QListWidget()
        layout.addWidget(self.expiring_policies_list)
        self.expiring_policies_list.itemDoubleClicked.connect(self.open_policy_detail)

        self.deal_reminders_label = QLabel("<b>Ближайшие 10 напоминаний по сделкам</b>")
        self.deal_reminders_label.setTextFormat(Qt.RichText)
        layout.addWidget(self.deal_reminders_label)
        self.deal_reminders_list = QListWidget()
        layout.addWidget(self.deal_reminders_list)
        self.deal_reminders_list.itemDoubleClicked.connect(self.open_deal_detail)

        layout.addStretch()
        self.update_stats()

    def update_stats(self):
        stats = get_basic_stats()
        html = (
            f"Клиентов: <b>{stats['clients']}</b><br>"
            f"Сделок: <b>{stats['deals']}</b><br>"
            f"Полисов: <b>{stats['policies']}</b><br>"
            f"Задач: <b>{stats['tasks']}</b>"
        )
        self.info_label.setText(html)

        sent_count = count_sent_tasks()
        work_count = count_working_tasks()
        confirm_count = count_unconfirmed_tasks()
        self.tg_tasks_label.setText(
            f"задач отправлено: <b>{sent_count}</b> штук<br>"
            f"задач в работе: <b>{work_count}</b> штук<br>"
            f"задач ожидают подтверждения: <b>{confirm_count}</b> штук"
        )

        self.upcoming_tasks_list.clear()
        tasks = get_upcoming_tasks()
        for t in tasks:
            note = (t.note or "").strip()
            short_note = note[:30] + ("…" if len(note) > 30 else "") if note else ""
            parts = [
                t.due_date.strftime("%d.%m.%Y"),
                t.title,
                short_note,
            ]
            if t.policy_id:
                parts.append(f"№{t.policy.policy_number}")
                if t.policy.client_id:
                    parts.append(t.policy.client.name)
            elif t.deal_id and t.deal.client_id:
                parts.append(t.deal.client.name)
            if t.deal_id:
                parts.append(t.deal.description)
            item = QListWidgetItem(" — ".join([p for p in parts if p]))
            item.setData(Qt.UserRole, t)
            self.upcoming_tasks_list.addItem(item)
        if not tasks:
            empty = QListWidgetItem("—")
            empty.setFlags(Qt.NoItemFlags)
            self.upcoming_tasks_list.addItem(empty)

        self.expiring_policies_list.clear()
        policies = get_expiring_policies()
        for p in policies:
            note = (p.note or "").strip()
            short_note = note[:30] + ("…" if len(note) > 30 else "") if note else ""
            parts = [
                p.end_date.strftime("%d.%m.%Y") if p.end_date else "",
                p.policy_number,
                short_note,
            ]
            if p.client_id:
                parts.append(p.client.name)
            if p.deal_id:
                parts.append(p.deal.description)
            item = QListWidgetItem(" — ".join([part for part in parts if part]))
            item.setData(Qt.UserRole, p)
            self.expiring_policies_list.addItem(item)
        if not policies:
            empty = QListWidgetItem("—")
            empty.setFlags(Qt.NoItemFlags)
            self.expiring_policies_list.addItem(empty)

        self.deal_reminders_list.clear()
        deals = get_upcoming_deal_reminders()
        for d in deals:
            parts = [
                d.reminder_date.strftime("%d.%m.%Y") if d.reminder_date else "",
                d.description,
            ]
            if d.client_id:
                parts.append(d.client.name)
            item = QListWidgetItem(" — ".join([part for part in parts if part]))
            item.setData(Qt.UserRole, d)
            self.deal_reminders_list.addItem(item)
        if not deals:
            empty = QListWidgetItem("—")
            empty.setFlags(Qt.NoItemFlags)
            self.deal_reminders_list.addItem(empty)

    def open_task_detail(self, item):
        task = item.data(Qt.UserRole)
        if task:
            dlg = TaskDetailView(task, parent=self)
            dlg.exec()
            self.update_stats()

    def open_policy_detail(self, item):
        policy = item.data(Qt.UserRole)
        if policy:
            dlg = PolicyDetailView(policy, parent=self)
            dlg.exec()
            self.update_stats()

    def open_deal_detail(self, item):
        deal = item.data(Qt.UserRole)
        if deal:
            dlg = DealDetailView(deal, parent=self)
            dlg.exec()
            self.update_stats()
