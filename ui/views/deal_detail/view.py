from collections.abc import Callable, Sequence
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.app_context import AppContext, get_app_context
from services.deal_metrics import get_deal_kpi_metrics
from utils.screen_utils import get_scaled_size
from utils.money import format_rub

from .actions import DealActionsMixin
from .tabs import DealTabsMixin
from .widgets import CollapsibleWidget, DealFilesPanel


class DealDetailView(DealTabsMixin, DealActionsMixin, QDialog):
    SETTINGS_KEY = "deal_detail_view"

    def __init__(self, deal, parent=None, *, context: AppContext | None = None):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)
        self.instance = deal
        self._context: AppContext | None = context or getattr(parent, "_context", None)
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
        self._tab_action_factories: dict[
            int, Callable[[], Sequence[QWidget]]
        ] = {}
        self._static_action_widgets: list[QWidget] = []
        self._tab_action_widgets: list[QWidget] = []

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

        self.files_panel = DealFilesPanel(self.left_panel)
        left_layout.addWidget(self.files_panel)

        self.create_folder_button = QPushButton("Создать/привязать")
        self.create_folder_button.clicked.connect(self._on_create_folder_clicked)
        left_layout.addWidget(self.create_folder_button)

        actions_panel = CollapsibleWidget("Действия", self.left_panel)
        self.primary_actions_layout = QVBoxLayout()
        self.primary_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.primary_actions_layout.setSpacing(12)
        actions_panel.setContentLayout(self.primary_actions_layout)
        left_layout.addWidget(actions_panel)
        self._update_files_panel()

        info_panel = self._create_info_panel()
        left_layout.addWidget(info_panel, stretch=1)
        left_layout.addStretch()

        self.splitter.addWidget(self.left_panel)

        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)


        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout.addWidget(self.tabs, 1)

        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self._init_tabs()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self._init_actions()
        self._register_shortcuts()
        self._apply_default_splitter_sizes(size.width())
        self._load_settings()

    def _get_context(self) -> AppContext:
        if self._context is None:
            self._context = get_app_context()
        return self._context

    def _get_drive_gateway(self):
        return self._get_context().drive_gateway

    def _on_tab_changed(self, index: int) -> None:
        """Refresh data when switching between tabs."""
        self._apply_tab_actions(index)

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

    def register_tab_actions(
        self,
        tab_index: int,
        widgets: Sequence[QWidget] | Callable[[], Sequence[QWidget]],
    ) -> None:
        if callable(widgets):
            factory = widgets
        else:
            frozen_widgets = tuple(widgets)

            def factory(
                _items: tuple[QWidget, ...] = frozen_widgets,
            ) -> Sequence[QWidget]:
                return list(_items)

        self._tab_action_factories[tab_index] = factory
        preferred_index: int | None = None
        if hasattr(self, "tabs"):
            preferred_index = self.tabs.currentIndex()
        if preferred_index is None:
            preferred_index = tab_index
        self._rebuild_tab_actions(preferred_index)

    def _apply_tab_actions(self, tab_index: int) -> None:
        self._rebuild_tab_actions(tab_index)

    def _rebuild_tab_actions(self, tab_index: int | None = None) -> None:
        group = getattr(self, "_tab_actions_group", None)
        if group is None:
            return

        self._tab_action_widgets = []

        target_index = tab_index
        if target_index is None and hasattr(self, "tabs"):
            target_index = self.tabs.currentIndex()

        ordered_indices: list[int] = []
        if (
            target_index is not None
            and target_index in self._tab_action_factories
        ):
            ordered_indices.append(target_index)

        if hasattr(self, "tabs"):
            for idx in range(self.tabs.count()):
                if idx == target_index:
                    continue
                if idx in self._tab_action_factories:
                    ordered_indices.append(idx)
        seen_indices = set(ordered_indices)
        for idx in self._tab_action_factories:
            if idx not in seen_indices:
                ordered_indices.append(idx)
                seen_indices.add(idx)

        new_widgets: list[QWidget] = []
        for idx in ordered_indices:
            factory = self._tab_action_factories.get(idx)
            if not factory:
                continue
            for widget in factory() or ():
                if widget in new_widgets:
                    continue
                new_widgets.append(widget)

        group.set_actions(new_widgets)
        group.setVisible(bool(new_widgets))
        self._tab_action_widgets = new_widgets

    def _init_kpi_panel(self):
        """(Re)populate the KPI panel without adding new duplicates."""
        while self.kpi_layout.count():
            item = self.kpi_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.net_profit_label = None

        deal_id = self.instance.id
        metrics = get_deal_kpi_metrics(deal_id)

        pol_open = metrics["policies_open"]
        pol_closed = metrics["policies_closed"]
        pay_open = metrics["payments_open"]
        pay_closed = metrics["payments_closed"]
        inc_open = metrics["incomes_open"]
        inc_closed = metrics["incomes_closed"]
        exp_open = metrics["expenses_open"]
        exp_closed = metrics["expenses_closed"]
        task_open = metrics["tasks_open"]
        task_closed = metrics["tasks_closed"]

        pay_expected = metrics["payments_expected"]
        pay_received = metrics["payments_received"]
        inc_expected = metrics["incomes_expected"]
        inc_received = metrics["incomes_received"]
        exp_planned = metrics["expenses_planned"]
        exp_spent = metrics["expenses_spent"]

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

        executor_name = metrics.get("executor_full_name")
        if executor_name:
            executor_label_text = (
                "Исполнитель: <span style='color:#d9534f;font-weight:bold'>"
                f"{executor_name}</span>"
            )
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
        total = max(total_width or self.width() or 1, 1)
        size_hint = self.left_panel.sizeHint().width() or 0
        min_width = max(1, self.left_panel.minimumSizeHint().width())
        fraction_width = max(1, int(total * 0.22))

        if size_hint:
            left = min(size_hint, fraction_width)
        else:
            left = fraction_width

        left = max(min_width, left)
        if left >= total:
            left = max(1, total - 1)

        right = max(1, total - left)
        self.splitter.setSizes([left, right])

    def _update_files_panel(self) -> None:
        """Обновить панель файлов и кнопку создания папки."""

        path = getattr(self.instance, "drive_folder_path", None)
        self.files_panel.set_folder(path)
        has_local_folder = bool(path and Path(path).is_dir())
        self.create_folder_button.setVisible(not has_local_folder)

    def _on_create_folder_clicked(self) -> None:
        """Создать или привязать локальную папку сделки."""

        self._ensure_local_folder()

    def _ensure_local_folder(self) -> str | None:  # type: ignore[override]
        """Ensure local folder exists and refresh related UI."""

        path = super()._ensure_local_folder()
        self._update_files_panel()
        return path
