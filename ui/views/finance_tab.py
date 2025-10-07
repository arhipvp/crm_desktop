from typing import Callable

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from core.app_context import AppContext
from ui.views.expense_table_view import ExpenseTableView
from ui.views.income_table_view import IncomeTableView
from ui.views.payment_table_view import PaymentTableView


class FinanceTab(QWidget):
    def __init__(
        self,
        parent=None,
        *,
        context: AppContext | None = None,
        payment_view_factory=PaymentTableView,
        income_view_factory=IncomeTableView,
        expense_view_factory=ExpenseTableView,
        autoload: bool = True,
    ):
        super().__init__(parent)
        self._context = context

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)

        self.payment_view = payment_view_factory(
            parent=self, context=self._context, autoload=autoload
        )
        self.income_view = income_view_factory(
            parent=self, context=self._context, autoload=autoload
        )
        self.expense_view = expense_view_factory(
            parent=self, context=self._context, autoload=autoload
        )

        self.tabs.addTab(self.payment_view, "Платежи")
        self.tabs.addTab(self.income_view, "Доходы")
        self.tabs.addTab(self.expense_view, "Расходы")

        self._loaded_tabs: dict[QWidget, bool] = {}
        self._data_loaded_handlers: list[Callable[[int], None]] = []
        for view in (self.payment_view, self.income_view, self.expense_view):
            self._loaded_tabs[view] = bool(getattr(view, "model", None))
            data_loaded = getattr(view, "data_loaded", None)
            connect = getattr(data_loaded, "connect", None)
            if callable(connect):
                handler = self._create_data_loaded_handler(view)
                connect(handler)
                self._data_loaded_handlers.append(handler)

        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.tabs.setCurrentIndex(0)

    def load_data(self) -> None:
        index = self.tabs.currentIndex()
        self._on_tab_changed(index)
        widget = self.tabs.widget(index)
        if widget is None:
            return
        if widget in self._loaded_tabs and not self._loaded_tabs[widget]:
            self._loaded_tabs[widget] = True

    def _create_data_loaded_handler(self, view: QWidget) -> Callable[[int], None]:
        def _handler(_count: int) -> None:
            self._loaded_tabs[view] = True

        return _handler

    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if widget is None:
            return
        if widget not in self._loaded_tabs:
            return
        if self._loaded_tabs[widget]:
            return
        load_data = getattr(widget, "load_data", None)
        if callable(load_data):
            load_data()
        else:
            self._loaded_tabs[widget] = True
