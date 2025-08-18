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

from services.deal_service import get_tasks_by_deal_id
from services.payment_service import get_payments_by_deal_id
from services.policy_service import get_policies_by_deal_id
from services.income_service import build_income_query
from services.expense_service import get_expenses_by_deal
from utils.screen_utils import get_scaled_size
from ui.forms.client_form import ClientForm

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

        self.header = QLabel(
            f"<h1><a href='#client'>{deal.client.name}</a> — Сделка #{deal.id}</h1>"
        )
        self.header.setTextFormat(Qt.RichText)
        self.header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.header.linkActivated.connect(self._on_client_link)
        self.layout.addWidget(self.header)

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

        cnt_policies = len(get_policies_by_deal_id(self.instance.id))
        cnt_payments = len(get_payments_by_deal_id(self.instance.id))
        cnt_tasks = len(get_tasks_by_deal_id(self.instance.id))
        cnt_income = build_income_query(deal_id=self.instance.id).count()
        cnt_expense = get_expenses_by_deal(self.instance.id).count()

        self.cnt_policies = cnt_policies
        self.cnt_payments = cnt_payments
        self.cnt_tasks = cnt_tasks
        self.cnt_income = cnt_income
        self.cnt_expense = cnt_expense

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

    def _on_client_link(self, _link: str) -> None:
        form = ClientForm(self.instance.client, parent=self)
        if form.exec():
            self.instance.client = form.instance
            self.setWindowTitle(
                f"Сделка #{self.instance.id} — {self.instance.client.name}: {self.instance.description}"
            )
            self.header.setText(
                f"<h1><a href='#client'>{self.instance.client.name}</a> — Сделка #{self.instance.id}</h1>"
            )
            self._init_kpi_panel()
            self._init_tabs()
