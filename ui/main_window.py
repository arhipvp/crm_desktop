import base64
import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QMainWindow,
    QTabWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)
from utils.screen_utils import get_scaled_size

from ui import settings as ui_settings

from ui.forms.import_policy_json_form import ImportPolicyJsonForm
from ui.main_menu import MainMenu
from ui.widgets.action_bar import ActionBar
from ui.views.client_table_view import ClientTableView
from ui.views.deal_table_view import DealTableView
from ui.views.finance_tab import FinanceTab
from ui.views.policy_table_view import PolicyTableView
from ui.views.task_table_view import TaskTableView
from ui.views.home_tab import HomeTab
from ui.views.executor_table_view import ExecutorTableView


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CRM Desktop")
        size = get_scaled_size(1600, 960, ratio=0.95)
        self.resize(size)
        self.setMinimumSize(800, 600)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Главное меню
        self.menu_bar = MainMenu(self)
        self.setMenuBar(self.menu_bar)

        self._action_widget_source = None
        self._action_widget_signal = None

        self.init_tabs()
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        self._load_settings()

    def init_tabs(self):
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.action_bar = ActionBar(central)
        layout.addWidget(self.action_bar)

        self.tab_widget = QTabWidget(central)
        layout.addWidget(self.tab_widget)
        self.setCentralWidget(central)
        self.home_tab = HomeTab()
        self.client_tab = ClientTableView()
        self.deal_tab = DealTableView()
        self.policy_tab = PolicyTableView()
        self.finance_tab = FinanceTab()
        self.task_tab = TaskTableView()

        self.tab_widget.addTab(self.home_tab, "Главная")
        self.tab_widget.addTab(self.client_tab, "Клиенты")
        self.tab_widget.addTab(self.deal_tab, "Сделки")
        self.tab_widget.addTab(self.policy_tab, "Полисы")
        self.tab_widget.addTab(self.finance_tab, "Финансы")
        self.tab_widget.addTab(self.task_tab, "Задачи")

        for tab in (
            self.client_tab,
            self.deal_tab,
            self.policy_tab,
            self.finance_tab,
            self.task_tab,
        ):
            if hasattr(tab, "data_loaded"):
                tab.data_loaded.connect(self.show_count)

        self._update_action_bar(self.tab_widget.currentWidget())

    def _load_settings(self):
        st = ui_settings.get_window_settings("MainWindow")
        geom = st.get("geometry")
        if geom:
            try:
                self.restoreGeometry(base64.b64decode(geom))
            except Exception:
                logger.exception("Не удалось восстановить геометрию окна")
        idx = st.get("last_tab")
        if idx is not None and 0 <= int(idx) < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(int(idx))
        if st.get("open_maximized"):
            self.setWindowState(self.windowState() | Qt.WindowMaximized)
        else:
            self.setWindowState(self.windowState() & ~Qt.WindowMaximized)

    def show_count(self, count: int):
        self.status_bar.showMessage(f"Записей: {count}")

    def on_tab_changed(self, index: int):
        widget = self.tab_widget.widget(index)
        self._update_action_bar(widget)
        if widget is self.home_tab:
            self.home_tab.update_stats()
            self.status_bar.clearMessage()

    def open_import_policy_json(self):
        dlg = ImportPolicyJsonForm(self)
        if dlg.exec() == QDialog.Accepted:
            # Уведомляем пользователя об успешном импорте
            self.status_bar.showMessage("Полис успешно импортирован", 5000)

    def open_reso_import(self):
        from ui.forms.reso_import_dialog import ResoImportDialog

        dlg = ResoImportDialog(parent=self)
        dlg.exec()

    def open_executors(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Исполнители")
        layout = QVBoxLayout(dlg)
        view = ExecutorTableView()
        layout.addWidget(view)
        dlg.resize(get_scaled_size(600, 400))
        dlg.exec()

    def open_settings(self):
        from ui.forms.settings_dialog import SettingsDialog

        dlg = SettingsDialog(self)
        dlg.exec()

    def export_current_view(self):
        widget = self.tab_widget.currentWidget()
        if widget and hasattr(widget, "export_csv"):
            widget.export_csv()

    def open_ai_consultant(self):
        from ui.forms.ai_consultant_dialog import AiConsultantDialog

        dlg = AiConsultantDialog(self)
        dlg.exec()

    def _update_action_bar(self, widget: QWidget | None) -> None:
        if self._action_widget_signal is not None:
            try:
                self._action_widget_signal.disconnect(self._on_action_widget_changed)
            except (TypeError, RuntimeError):
                pass
        self._action_widget_source = None
        self._action_widget_signal = None

        action_widget = None
        if widget is not None:
            getter = getattr(widget, "get_action_widget", None)
            if callable(getter):
                action_widget = getter()

            signal = getattr(widget, "action_widget_changed", None)
            if signal is not None:
                try:
                    signal.connect(self._on_action_widget_changed)
                    self._action_widget_source = widget
                    self._action_widget_signal = signal
                except (TypeError, RuntimeError):
                    self._action_widget_source = None
                    self._action_widget_signal = None

        self.action_bar.set_widget(action_widget)

    def _on_action_widget_changed(self, widget: QWidget | None) -> None:
        if widget is None and self._action_widget_source is not None:
            getter = getattr(self._action_widget_source, "get_action_widget", None)
            if callable(getter):
                widget = getter()
        self.action_bar.set_widget(widget)

    def closeEvent(self, event):
        st = ui_settings.get_window_settings("MainWindow")
        st.update(
            {
                "geometry": base64.b64encode(self.saveGeometry()).decode("ascii"),
                "last_tab": self.tab_widget.currentIndex(),
            }
        )
        ui_settings.set_window_settings("MainWindow", st)
        super().closeEvent(event)
