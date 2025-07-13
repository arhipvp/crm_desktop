from PySide6.QtWidgets import (
    QDialog,
    QMainWindow,
    QTabWidget,
    QStatusBar,
    QVBoxLayout,
)
from utils.screen_utils import get_scaled_size

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

    def show_count(self, count: int):
        self.status_bar.showMessage(f"Записей: {count}")

    def on_tab_changed(self, index: int):
        widget = self.tab_widget.widget(index)
        if widget is self.home_tab:
            self.home_tab.update_stats()
            self.status_bar.clearMessage()

    def open_import_policy_json(self):
        while True:
            dlg = ImportPolicyJsonForm(self)
            if dlg.exec() != QDialog.Accepted:
                break

    def open_reso_import(self):
        from PySide6.QtWidgets import QFileDialog
        from ui.forms.reso_import_dialog import ResoImportDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите таблицу RESO", "", "Excel/CSV (*.xlsx *.xls *.csv *.tsv)"
        )
        if file_path:
            dlg = ResoImportDialog(file_path, self)
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

    def open_ai_consultant(self):
        from ui.forms.ai_consultant_dialog import AiConsultantDialog

        dlg = AiConsultantDialog(self)
        dlg.exec()
