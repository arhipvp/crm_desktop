from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from ui.views.expense_table_view import ExpenseTableView
from ui.views.income_table_view import IncomeTableView
from ui.views.payment_table_view import PaymentTableView


class FinanceTab(QWidget):
    action_widget_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)

        self.payment_view = PaymentTableView()
        self.income_view = IncomeTableView()
        self.expense_view = ExpenseTableView()

        self.tabs.addTab(self.payment_view, "Платежи")
        self.tabs.addTab(self.income_view, "Доходы")
        self.tabs.addTab(self.expense_view, "Расходы")

        self._subtab_action_signal = None
        self.tabs.currentChanged.connect(self._on_subtab_changed)
        self._on_subtab_changed(self.tabs.currentIndex())

    def get_action_widget(self) -> QWidget | None:
        current = self.tabs.currentWidget()
        getter = getattr(current, "get_action_widget", None) if current else None
        return getter() if callable(getter) else None

    def _on_subtab_changed(self, index: int) -> None:
        if self._subtab_action_signal is not None:
            try:
                self._subtab_action_signal.disconnect(self._on_child_action_widget_changed)
            except (TypeError, RuntimeError):
                pass
            self._subtab_action_signal = None

        current = self.tabs.widget(index)
        if current is not None:
            signal = getattr(current, "action_widget_changed", None)
            if signal is not None:
                try:
                    signal.connect(self._on_child_action_widget_changed)
                    self._subtab_action_signal = signal
                except (TypeError, RuntimeError):
                    self._subtab_action_signal = None

        self._emit_action_widget_changed()

    def _on_child_action_widget_changed(self, widget: QWidget | None) -> None:
        if widget is None:
            widget = self.get_action_widget()
        self.action_widget_changed.emit(widget)

    def _emit_action_widget_changed(self) -> None:
        self.action_widget_changed.emit(self.get_action_widget())
