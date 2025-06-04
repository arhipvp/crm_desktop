from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

from database.models import Client, Deal, Policy, Task


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

        self.upcoming_tasks_label = QLabel()
        self.upcoming_tasks_label.setTextFormat(Qt.RichText)
        layout.addWidget(self.upcoming_tasks_label)

        self.expiring_policies_label = QLabel()
        self.expiring_policies_label.setTextFormat(Qt.RichText)
        layout.addWidget(self.expiring_policies_label)

        self.deal_reminders_label = QLabel()
        self.deal_reminders_label.setTextFormat(Qt.RichText)
        layout.addWidget(self.deal_reminders_label)

        layout.addStretch()
        self.update_stats()

    def update_stats(self):
        client_count = Client.select().where(Client.is_deleted == False).count()
        deal_count = Deal.select().where(Deal.is_deleted == False).count()
        policy_count = Policy.select().where(Policy.is_deleted == False).count()
        task_count = Task.select().where(Task.is_deleted == False).count()
        html = (
            f"Клиентов: <b>{client_count}</b><br>"
            f"Сделок: <b>{deal_count}</b><br>"
            f"Полисов: <b>{policy_count}</b><br>"
            f"Задач: <b>{task_count}</b>"
        )
        self.info_label.setText(html)

        tg_count = (
            Task
            .select()
            .where(
                (Task.dispatch_state == "sent") &
                (Task.is_deleted == False) &
                (Task.is_done == False)
            )
            .count()
        )
        self.tg_tasks_label.setText(
            f"Задач в работе у помощника: <b>{tg_count}</b>"
        )

        tasks = (
            Task
            .select()
            .where((Task.is_done == False) & (Task.is_deleted == False))
            .order_by(Task.due_date.asc())
            .limit(10)
        )
        task_lines = [
            f"{t.due_date.strftime('%d.%m.%Y')} — {t.title}" for t in tasks
        ]
        self.upcoming_tasks_label.setText(
            "<b>Ближайшие 10 задач</b><br>" + ("<br>".join(task_lines) or "—")
        )

        policies = (
            Policy
            .select()
            .where(
                (Policy.is_deleted == False) &
                (Policy.end_date.is_null(False))
            )
            .order_by(Policy.end_date.asc())
            .limit(10)
        )
        policy_lines = [
            f"{p.end_date.strftime('%d.%m.%Y')} — {p.policy_number}" for p in policies
        ]
        self.expiring_policies_label.setText(
            "<b>Ближайшие 10 заканчивающихся полисов</b><br>" +
            ("<br>".join(policy_lines) or "—")
        )

        deals = (
            Deal
            .select()
            .where(
                (Deal.is_deleted == False) &
                (Deal.is_closed == False) &
                (Deal.reminder_date.is_null(False))
            )
            .order_by(Deal.reminder_date.asc())
            .limit(10)
        )
        deal_lines = [
            f"{d.reminder_date.strftime('%d.%m.%Y')} — {d.description}" for d in deals
        ]
        self.deal_reminders_label.setText(
            "<b>Ближайшие 10 напоминаний по сделкам</b><br>" +
            ("<br>".join(deal_lines) or "—")
        )
