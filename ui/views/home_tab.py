from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtCharts import (
    QChart,
    QChartView,
    QBarSeries,
    QBarSet,
    QBarCategoryAxis,
    QValueAxis,
)

from core.app_context import AppContext, get_app_context
from services.dashboard_service import (
    get_dashboard_counters,
    get_upcoming_tasks,
    get_expiring_policies,
    get_upcoming_deal_reminders,
    get_deal_reminder_counts,
)

from ui.views.task_detail_view import TaskDetailView
from ui.views.policy_detail_view import PolicyDetailView
from ui.views.deal_detail import DealDetailView


class HomeTab(QWidget):
    """Стартовая страница со сводной информацией."""

    def __init__(self, parent=None, *, context: AppContext | None = None):
        super().__init__(parent)
        self._context: AppContext | None = context
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

        self.reminder_chart_label = QLabel(
            "<b>Напоминания по сделкам на 2 недели</b>"
        )
        self.reminder_chart_label.setTextFormat(Qt.RichText)
        layout.addWidget(self.reminder_chart_label)
        self.reminder_chart = QChartView()
        self.reminder_chart.setMinimumHeight(200)
        layout.addWidget(self.reminder_chart)

        layout.addStretch()
        self.update_stats()

    def update_stats(self):
        counters = get_dashboard_counters()
        stats = counters["entities"]
        html = (
            f"Клиентов: <b>{stats['clients']}</b><br>"
            f"Сделок: <b>{stats['deals']}</b><br>"
            f"Полисов: <b>{stats['policies']}</b><br>"
            f"Задач: <b>{stats['tasks']}</b>"
        )
        self.info_label.setText(html)

        task_counters = counters["tasks"]
        sent_count = task_counters["sent"]
        work_count = task_counters["working"]
        confirm_count = task_counters["unconfirmed"]
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

        self.update_reminder_chart()

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
            dlg = DealDetailView(
                deal,
                parent=self,
                context=self._get_context(),
            )
            dlg.exec()
            self.update_stats()

    def _get_context(self) -> AppContext:
        if self._context is None:
            self._context = get_app_context()
        return self._context

    def update_reminder_chart(self):
        counts = get_deal_reminder_counts()
        chart = QChart()
        bar_set = QBarSet("Напоминания")
        categories = []
        for d in sorted(counts.keys()):
            bar_set.append(counts[d])
            categories.append(d.strftime("%d.%m"))
        series = QBarSeries()
        series.append(bar_set)
        chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setRange(0, max(counts.values()) if counts else 0)
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)

        chart.legend().setVisible(False)
        chart.setAnimationOptions(QChart.SeriesAnimations)
        self.reminder_chart.setChart(chart)
        self.reminder_chart.setRenderHint(QPainter.Antialiasing)

