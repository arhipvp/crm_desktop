from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

from services.dashboard_service import (
    get_basic_stats,
    count_assistant_tasks,
    get_upcoming_tasks,
    get_expiring_policies,
    get_upcoming_deal_reminders,
)


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
        stats = get_basic_stats()
        html = (
            f"Клиентов: <b>{stats['clients']}</b><br>"
            f"Сделок: <b>{stats['deals']}</b><br>"
            f"Полисов: <b>{stats['policies']}</b><br>"
            f"Задач: <b>{stats['tasks']}</b>"
        )
        self.info_label.setText(html)

        tg_count = count_assistant_tasks()
        self.tg_tasks_label.setText(
            f"Задач в работе у помощника: <b>{tg_count}</b>"
        )

        task_lines = []
        for t in get_upcoming_tasks():
            note = (t.note or "").strip()
            short_note = note[:30] + ("…" if len(note) > 30 else "") if note else ""
            parts = [
                t.due_date.strftime('%d.%m.%Y'),
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
            task_lines.append(" — ".join([p for p in parts if p]))
        self.upcoming_tasks_label.setText(
            "<b>Ближайшие 10 задач</b><br>" + ("<br>".join(task_lines) or "—")
        )

        policy_lines = []
        for p in get_expiring_policies():
            note = (p.note or "").strip()
            short_note = note[:30] + ("…" if len(note) > 30 else "") if note else ""
            parts = [
                p.end_date.strftime('%d.%m.%Y') if p.end_date else '',
                p.policy_number,
                short_note,
            ]
            if p.client_id:
                parts.append(p.client.name)
            if p.deal_id:
                parts.append(p.deal.description)
            policy_lines.append(" — ".join([part for part in parts if part]))
        self.expiring_policies_label.setText(
            "<b>Ближайшие 10 заканчивающихся полисов</b><br>" +
            ("<br>".join(policy_lines) or "—")
        )

        deal_lines = []
        for d in get_upcoming_deal_reminders():
            parts = [
                d.reminder_date.strftime('%d.%m.%Y') if d.reminder_date else '',
                d.description,
            ]
            if d.client_id:
                parts.append(d.client.name)
            deal_lines.append(" — ".join([part for part in parts if part]))
        self.deal_reminders_label.setText(
            "<b>Ближайшие 10 напоминаний по сделкам</b><br>" +
            ("<br>".join(deal_lines) or "—")
        )
