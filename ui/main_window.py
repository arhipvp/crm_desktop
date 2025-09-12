import base64

from PySide6.QtWidgets import (
    QDialog,
    QMainWindow,
    QTabWidget,
    QStatusBar,
    QVBoxLayout,
)
from utils.screen_utils import get_scaled_size

from ui import settings as ui_settings

from ui.forms.import_policy_json_form import ImportPolicyJsonForm
from ui.main_menu import MainMenu
from ui.views.client_table_view import ClientTableView
from ui.views.deal_table_view import DealTableView
from ui.views.finance_tab import FinanceTab
from ui.views.policy_table_view import PolicyTableView
from ui.views.task_table_view import TaskTableView
from ui.views.home_tab import HomeTab
from ui.views.executor_table_view import ExecutorTableView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CRM Desktop")
        size = get_scaled_size(1300, 850)
        self.resize(size)
        self.setMinimumSize(800, 600)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Главное меню
        self.menu_bar = MainMenu(self)
        self.setMenuBar(self.menu_bar)

        self.init_tabs()
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        self._load_settings()

    def init_tabs(self):
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
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

    def _load_settings(self):
        st = ui_settings.get_window_settings("MainWindow")
        geom = st.get("geometry")
        if geom:
            try:
                self.restoreGeometry(base64.b64decode(geom))
            except Exception:
                pass
        idx = st.get("last_tab")
        if idx is not None and 0 <= int(idx) < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(int(idx))

    def show_count(self, count: int):
        self.status_bar.showMessage(f"Записей: {count}")

    def on_tab_changed(self, index: int):
        widget = self.tab_widget.widget(index)
        if widget is self.home_tab:
            self.home_tab.update_stats()
            self.status_bar.clearMessage()

    def open_import_policy_json(self):
        dlg = ImportPolicyJsonForm(self)
        # Повторяем импорт, пока пользователь не отменит диалог
        while dlg.exec() == QDialog.Accepted:
            self.status_bar.showMessage("Полис успешно импортирован", 5000)
            dlg = ImportPolicyJsonForm(self)

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

    def closeEvent(self, event):
        st = {
            "geometry": base64.b64encode(self.saveGeometry()).decode("ascii"),
            "last_tab": self.tab_widget.currentIndex(),
        }
        ui_settings.set_window_settings("MainWindow", st)
        super().closeEvent(event)
