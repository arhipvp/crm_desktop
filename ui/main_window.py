from PySide6.QtWidgets import QDialog, QMainWindow, QMessageBox, QTabWidget

from ui.forms.import_policy_json_form import ImportPolicyJsonForm
from ui.main_menu import MainMenu
from ui.views.client_table_view import ClientTableView
from ui.views.deal_table_view import DealTableView
from ui.views.expense_table_view import ExpenseTableView
from ui.views.finance_tab import FinanceTab
from ui.views.income_table_view import IncomeTableView
from ui.views.payment_table_view import PaymentTableView
from ui.views.policy_table_view import PolicyTableView
from ui.views.task_table_view import TaskTableView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CRM Desktop")
        self.resize(1300, 850)

        # Главное меню
        self.menu_bar = MainMenu(self)
        self.setMenuBar(self.menu_bar)

        # Вкладки
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.init_tabs()

    def init_tabs(self):
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        self.client_tab = ClientTableView()
        self.deal_tab = DealTableView()
        self.policy_tab = PolicyTableView()
        self.finance_tab = FinanceTab()
        self.task_tab = TaskTableView()


        self.tab_widget.addTab(self.client_tab, "Клиенты")
        self.tab_widget.addTab(self.deal_tab, "Сделки")
        self.tab_widget.addTab(self.policy_tab, "Полисы")
        self.tab_widget.addTab(self.finance_tab, "Финансы")
        self.tab_widget.addTab(self.task_tab, "Задачи")
    
    def open_import_policy_json(self):

        while True:
            dlg = ImportPolicyJsonForm(self)
            if dlg.exec() != QDialog.Accepted:
                break








