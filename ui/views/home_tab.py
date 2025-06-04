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
