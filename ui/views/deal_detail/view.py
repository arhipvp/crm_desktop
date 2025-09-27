from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from services.task_crud import get_task_counts_by_deal_id
from services.payment_service import (
    get_payment_amounts_by_deal_id,
    get_payment_counts_by_deal_id,
)
from services.policies import get_policy_counts_by_deal_id
from services.income_service import (
    get_income_amounts_by_deal_id,
    get_income_counts_by_deal_id,
)
from services.expense_service import (
    get_expense_amounts_by_deal_id,
    get_expense_counts_by_deal_id,
)
from utils.screen_utils import get_scaled_size
from utils.money import format_rub

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

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.layout.addWidget(self.splitter, stretch=1)

        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        self.net_profit_label: QLabel | None = None

        status = self.instance.status or "Без статуса"
        color_map = {"Закрыта": "#d9534f", "Активна": "#5cb85c"}
        color = color_map.get(status, "#6c757d")
        header = QLabel(
            f"<h1><span style='background:{color};padding:2px 6px;color:#fff'>"
            f"{status}</span> Сделка #{deal.id}</h1>"
        )
        header.setTextFormat(Qt.RichText)
        header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header.setWordWrap(True)
        left_layout.addWidget(header)

        self.kpi_container = QWidget()
        self.kpi_layout = QHBoxLayout(self.kpi_container)
        self.kpi_layout.setContentsMargins(0, 0, 0, 0)
        self.kpi_layout.setSpacing(8)
        left_layout.addWidget(self.kpi_container)
        self._init_kpi_panel()

        info_panel = self._create_info_panel()
        left_layout.addWidget(info_panel, stretch=1)
        left_layout.addStretch()

        self.splitter.addWidget(self.left_panel)

        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.splitter.addWidget(self.tabs)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self._init_tabs()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self._init_actions()
        self._register_shortcuts()
        self._apply_default_splitter_sizes(size.width())
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
        self.net_profit_label = None

        deal_id = self.instance.id
        pol_open, pol_closed = get_policy_counts_by_deal_id(deal_id)
        pay_open, pay_closed = get_payment_counts_by_deal_id(deal_id)
        inc_open, inc_closed = get_income_counts_by_deal_id(deal_id)
        exp_open, exp_closed = get_expense_counts_by_deal_id(deal_id)
        task_open, task_closed = get_task_counts_by_deal_id(deal_id)

        pay_expected, pay_received = get_payment_amounts_by_deal_id(deal_id)
        inc_expected, inc_received = get_income_amounts_by_deal_id(deal_id)
        exp_planned, exp_spent = get_expense_amounts_by_deal_id(deal_id)

        cnt_policies = pol_open + pol_closed
        cnt_payments = pay_open + pay_closed
        cnt_income = inc_open + inc_closed
        cnt_expense = exp_open + exp_closed
        cnt_tasks = task_open + task_closed

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

        payments_text = (
            f"Платежи: <b>{cnt_payments}</b> — ожидается "
            f"{format_rub(pay_expected)}, получено {format_rub(pay_received)}"
        )
        incomes_text = (
            f"Доходы: <b>{cnt_income}</b> — ожидается "
            f"{format_rub(inc_expected)}, получено {format_rub(inc_received)}"
        )
        expenses_text = (
            f"Расходы: <b>{cnt_expense}</b> — запланировано "
            f"{format_rub(exp_planned)}, списано {format_rub(exp_spent)}"
        )
        net_profit = inc_received - exp_spent
        self.net_profit_label = QLabel(
            f"Чистая прибыль: <b>{format_rub(net_profit)}</b>"
        )
        self.net_profit_label.setTextFormat(Qt.RichText)
        self._apply_net_profit_style(net_profit)

        from services import executor_service as es

        ex = es.get_executor_for_deal(self.instance.id)
        executor_name = ex.full_name if ex else "—"
        if ex:
            executor_label_text = f"Исполнитель: <b>{executor_name}</b>"
        else:
            executor_label_text = (
                "Исполнитель: <span style='color:#d9534f; font-weight:bold'>"
                "не назначен</span>"
            )

        for text in [
            f"Полисов: <b>{cnt_policies}</b>",
            payments_text,
            incomes_text,
            expenses_text,
        ]:
            lbl = QLabel(text)
            lbl.setTextFormat(Qt.RichText)
            self.kpi_layout.addWidget(lbl)

        if self.net_profit_label:
            self.kpi_layout.addWidget(self.net_profit_label)

        for text in [
            f"Задач: <b>{cnt_tasks}</b>",
            executor_label_text,
        ]:
            lbl = QLabel(text)
            lbl.setTextFormat(Qt.RichText)
            self.kpi_layout.addWidget(lbl)
        self.kpi_layout.addStretch()

        if hasattr(self, "tabs"):
            self._update_tab_titles()

    def _apply_net_profit_style(self, net_profit: float | int) -> None:
        """Update the appearance of the net profit label based on value."""
        if not self.net_profit_label:
            return

        if net_profit > 0:
            color = "#28a745"
        elif net_profit < 0:
            color = "#dc3545"
        else:
            color = "#6c757d"

        self.net_profit_label.setStyleSheet(
            f"color: {color}; font-weight: 600;"
        )

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

    def _apply_default_splitter_sizes(self, total_width: int | None = None) -> None:
        total = total_width or self.width() or 1
        left = int(total * 0.35)
        right = max(1, total - left)
        self.splitter.setSizes([left, right])
