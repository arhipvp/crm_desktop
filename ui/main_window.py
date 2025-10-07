import base64
import logging

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtWidgets import (
    QDialog,
    QMainWindow,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
)

from core.app_context import AppContext, get_app_context
from utils.screen_utils import get_scaled_size

from ui import settings as ui_settings

from ui.forms.import_policy_json_form import ImportPolicyJsonForm
from ui.main_menu import MainMenu
from ui.views.client_table_view import ClientTableView
from ui.views.deal_table_view import DealTableView
from ui.views.executor_table_view import ExecutorTableView
from ui.views.finance_tab import FinanceTab
from ui.views.home_tab import HomeTab
from ui.views.policy_table_view import PolicyTableView
from ui.views.task_table_view import TaskTableView


logger = logging.getLogger(__name__)


EXECUTOR_DIALOG_SETTINGS_KEY = "executor_dialog"


def apply_main_window_settings(
    settings: dict,
    tab_widget,
    restore_geometry,
    window_state_getter,
    set_window_state,
    *,
    logger_: logging.Logger | None = None,
):
    logger_ = logger_ or logger
    geom = settings.get("geometry")
    if geom:
        try:
            restore_geometry(base64.b64decode(geom))
        except Exception:  # pragma: no cover - логирование ошибки
            logger_.exception("Не удалось восстановить геометрию окна")
    idx = settings.get("last_tab")
    if idx is not None:
        try:
            idx_int = int(idx)
        except (TypeError, ValueError):
            idx_int = None
        if idx_int is not None and 0 <= idx_int < tab_widget.count():
            tab_widget.setCurrentIndex(idx_int)
    if "open_maximized" in settings:
        current_state = window_state_getter()
        if settings.get("open_maximized"):
            set_window_state(current_state | Qt.WindowMaximized)
        else:
            set_window_state(current_state & ~Qt.WindowMaximized)


def run_import_policy_dialog(
    dialog_factory,
    status_bar,
    *,
    accepted_value: int = QDialog.Accepted,
    success_message: str = "Полис успешно импортирован",
    message_timeout_ms: int = 5000,
):
    dialog = dialog_factory()
    result = dialog.exec()
    if result == accepted_value:
        status_bar.showMessage(success_message, message_timeout_ms)
    return result


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        context: AppContext | None = None,
        settings_applier=apply_main_window_settings,
        import_policy_runner=run_import_policy_dialog,
    ):
        super().__init__()
        self._context = context or get_app_context()
        self._settings_applier = settings_applier
        self._import_policy_runner = import_policy_runner
        self.setWindowTitle("CRM Desktop")
        size = get_scaled_size(1600, 960, ratio=0.95)
        self.resize(size)
        self.setMinimumSize(800, 600)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Главное меню
        self.menu_bar = MainMenu(self)
        self.setMenuBar(self.menu_bar)

        self._pending_tab_loads: set[int] = set()
        self.init_tabs()
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        self._load_settings()

    def init_tabs(self):
        self.tab_widget = QTabWidget(self)
        self.setCentralWidget(self.tab_widget)
        self.home_tab = HomeTab(context=self._context)
        self.client_tab = ClientTableView(
            parent=self, context=self._context, autoload=False
        )
        self.deal_tab = DealTableView(parent=self, context=self._context, autoload=False)
        self.policy_tab = PolicyTableView(
            parent=self, context=self._context, autoload=False
        )
        self.finance_tab = FinanceTab(parent=self, context=self._context, autoload=False)
        self.task_tab = TaskTableView(parent=self, context=self._context, autoload=False)

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

        self._pending_tab_loads = {
            id(tab)
            for tab in (
                self.client_tab,
                self.deal_tab,
                self.policy_tab,
                self.finance_tab,
                self.task_tab,
            )
            if hasattr(tab, "load_data")
        }

    def _load_settings(self):
        st = ui_settings.get_window_settings("MainWindow")
        self._settings_applier(
            st,
            self.tab_widget,
            self.restoreGeometry,
            self.windowState,
            self.setWindowState,
        )

    def show_count(self, count: int):
        self.status_bar.showMessage(f"Записей: {count}")

    def on_tab_changed(self, index: int):
        widget = self.tab_widget.widget(index)
        if widget is self.home_tab:
            self.home_tab.update_stats()
            self.status_bar.clearMessage()
            return

        widget_id = id(widget)
        if hasattr(widget, "load_data") and widget_id in self._pending_tab_loads:
            widget.load_data()
            self._pending_tab_loads.discard(widget_id)

    def open_import_policy_json(self):
        return self._import_policy_runner(
            lambda: ImportPolicyJsonForm(self),
            self.status_bar,
        )

    def open_reso_import(self):
        from ui.forms.reso_import_dialog import ResoImportDialog

        dlg = ResoImportDialog(parent=self)
        dlg.exec()

    def open_executors(self):
        dlg = QDialog(self)
        dlg.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)
        dlg.setWindowTitle("Исполнители")
        layout = QVBoxLayout(dlg)
        view = ExecutorTableView(parent=dlg, context=self._context)
        layout.addWidget(view)
        dlg.resize(get_scaled_size(600, 400))
        geometry = (
            ui_settings.get_window_settings(EXECUTOR_DIALOG_SETTINGS_KEY).get("geometry")
        )
        if geometry:
            try:
                decoded_geometry = base64.b64decode(geometry)
                dlg.restoreGeometry(QByteArray(decoded_geometry))
            except Exception:
                logger.exception(
                    "Не удалось восстановить геометрию диалога исполнителей"
                )

        dlg.exec()
        geometry_bytes = bytes(dlg.saveGeometry())
        encoded_geometry = base64.b64encode(geometry_bytes).decode("ascii")
        ui_settings.set_window_settings(
            EXECUTOR_DIALOG_SETTINGS_KEY, {"geometry": encoded_geometry}
        )

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
