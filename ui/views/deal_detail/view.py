from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
)

from services.task_service import get_task_counts_by_deal_id
from services.payment_service import get_payment_counts_by_deal_id
from services.policies import get_policy_counts_by_deal_id
from services.income_service import get_income_counts_by_deal_id
from services.expense_service import get_expense_counts_by_deal_id
from utils.screen_utils import get_scaled_size

from .actions import DealActionsMixin
from .tabs import DealTabsMixin


class DealDetailView(DealTabsMixin, DealActionsMixin, QDialog):
    SETTINGS_KEY = "deal_detail_view"

    def __init__(self, deal, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)
        self.instance = deal
        self.setAcceptDrops(True)
        self.setWindowTitle(
            f"Сделка #{deal.id} — {deal.client.name}: {deal.description}"
        )
        size = get_scaled_size(1600, 900)
        self.resize(size)
        min_w = max(900, int(size.width() * 0.8))
        self.setMinimumSize(min_w, 480)

        self.layout = QVBoxLayout(self)
        self._shortcuts: list[QShortcut] = []

        status = self.instance.status or "Без статуса"
        color_map = {"Закрыта": "#d9534f", "Активна": "#5cb85c"}
        color = color_map.get(status, "#6c757d")
        header = QLabel(
            f"<h1><span style='background:{color};padding:2px 6px;color:#fff'>"
            f"{status}</span> Сделка #{deal.id}</h1>"
        )
        header.setTextFormat(Qt.RichText)
        header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.layout.addWidget(header)

        self.kpi_layout = QHBoxLayout()
        self.layout.addLayout(self.kpi_layout)
        self._init_kpi_panel()

        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs, stretch=1)
        self._init_tabs()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self._init_actions()
        self._register_shortcuts()
        self._load_settings()

    def _on_tab_changed(self, index: int) -> None:
        """Refresh data when switching between tabs."""
        if index == getattr(self, "policy_tab_idx", None) and hasattr(self, "pol_view"):
            self.pol_view.refresh()
        elif index == getattr(self, "payment_tab_idx", None) and hasattr(self, "pay_view"):
            self.pay_view.refresh()
        elif index == getattr(self, "income_tab_idx", None) and hasattr(self, "income_view"):
            self.income_view.refresh()
        elif index == getattr(self, "expense_tab_idx", None) and hasattr(self, "expense_view"):
            self.expense_view.refresh()
        elif index == getattr(self, "task_tab_idx", None) and hasattr(self, "task_view"):
            self.task_view.refresh()
        else:
            return

        self._init_kpi_panel()

    def _init_kpi_panel(self):
        """(Re)populate the KPI panel without adding new duplicates."""
        while self.kpi_layout.count():
            item = self.kpi_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        pol_open, pol_closed = get_policy_counts_by_deal_id(self.instance.id)
        pay_open, pay_closed = get_payment_counts_by_deal_id(self.instance.id)
        task_open, task_closed = get_task_counts_by_deal_id(self.instance.id)
        inc_open, inc_closed = get_income_counts_by_deal_id(self.instance.id)
        exp_open, exp_closed = get_expense_counts_by_deal_id(self.instance.id)

        cnt_policies = pol_open + pol_closed
        cnt_payments = pay_open + pay_closed
        cnt_tasks = task_open + task_closed
        cnt_income = inc_open + inc_closed
        cnt_expense = exp_open + exp_closed

        self.cnt_policies_open = pol_open
        self.cnt_policies_closed = pol_closed
        self.cnt_payments_open = pay_open
        self.cnt_payments_closed = pay_closed
        self.cnt_tasks_open = task_open
        self.cnt_tasks_closed = task_closed
        self.cnt_income_open = inc_open
        self.cnt_income_closed = inc_closed
        self.cnt_expense_open = exp_open
        self.cnt_expense_closed = exp_closed

        from services import executor_service as es

        ex = es.get_executor_for_deal(self.instance.id)
        executor_name = ex.full_name if ex else "—"

        for text in [
            f"Полисов: <b>{cnt_policies}</b>",
            f"Платежей: <b>{cnt_payments}</b>",
            f"Доходов: <b>{cnt_income}</b>",
            f"Расходов: <b>{cnt_expense}</b>",
            f"Задач: <b>{cnt_tasks}</b>",
            f"<span style='color:red; font-weight:bold'>Исполнитель: {executor_name}</span>",
        ]:
            lbl = QLabel(text)
            lbl.setTextFormat(Qt.RichText)
            self.kpi_layout.addWidget(lbl)
        self.kpi_layout.addStretch()

        if hasattr(self, "tabs"):
            self._update_tab_titles()

    def _update_tab_titles(self) -> None:
        """Обновить заголовки вкладок с актуальными счётчиками."""
        if getattr(self, "policy_tab_idx", None) is not None:
            self.tabs.setTabText(
                self.policy_tab_idx,
                f"Полисы {self.cnt_policies_open} ({self.cnt_policies_closed})",
            )
        if getattr(self, "payment_tab_idx", None) is not None:
            self.tabs.setTabText(
                self.payment_tab_idx,
                f"Платежи {self.cnt_payments_open} ({self.cnt_payments_closed})",
            )
        if getattr(self, "income_tab_idx", None) is not None:
            self.tabs.setTabText(
                self.income_tab_idx,
                f"Доходы {self.cnt_income_open} ({self.cnt_income_closed})",
            )
        if getattr(self, "expense_tab_idx", None) is not None:
            self.tabs.setTabText(
                self.expense_tab_idx,
                f"Расходы {self.cnt_expense_open} ({self.cnt_expense_closed})",
            )
        if getattr(self, "task_tab_idx", None) is not None:
            self.tabs.setTabText(
                self.task_tab_idx,
                f"Задачи {self.cnt_tasks_open} ({self.cnt_tasks_closed})",
            )
