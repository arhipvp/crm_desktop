from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QCheckBox,
    QScrollArea,
)

from services.clients import get_clients_page
from ui.widgets.client_card import ClientCard
from ui.forms.client_form import ClientForm
from ui.common.paginator import Paginator


class ClientView(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)

        # Параметры пагинации
        self.current_page = 1
        self.per_page = 50

        # Верхняя панель управления
        control_layout = QHBoxLayout()

        self.add_btn = QPushButton("➕ Добавить клиента")
        self.add_btn.clicked.connect(self.add_client)
        control_layout.addWidget(self.add_btn)

        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self.load_clients)
        control_layout.addWidget(self.refresh_btn)

        self.show_deleted_checkbox = QCheckBox("Показывать удалённых")
        self.show_deleted_checkbox.setChecked(False)
        self.show_deleted_checkbox.stateChanged.connect(self.reset_pagination)
        control_layout.addWidget(self.show_deleted_checkbox)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по имени клиента...")
        self.search_input.textChanged.connect(self.reset_pagination)
        control_layout.addWidget(self.search_input)

        control_layout.addStretch()
        self.layout.addLayout(control_layout)

        # Скроллируемая область
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.scroll.setWidget(self.content)

        self.layout.addWidget(self.scroll)

        # Пагинация внизу
        self.paginator = Paginator(self.next_page, self.prev_page, per_page=self.per_page)
        self.layout.addWidget(self.paginator)

        self.load_clients()

    def reset_pagination(self):
        self.current_page = 1
        self.load_clients()

    def load_clients(self):
        search_text = self.search_input.text().strip().lower()
        show_deleted = self.show_deleted_checkbox.isChecked()

        clients = list(
            get_clients_page(
                self.current_page, self.per_page, search_text, show_deleted
            )
        )
        self.clients = clients
        self.render_clients(clients)
        self.paginator.update_page(
            self.current_page, len(clients), self.per_page
        )

    def render_clients(self, clients):
        for i in reversed(range(self.content_layout.count())):
            widget = self.content_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        for client in clients:
            card = ClientCard(client, parent=self)
            self.content_layout.addWidget(card)

        self.content_layout.addStretch()

    def next_page(self):
        self.current_page += 1
        self.load_clients()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_clients()

    def add_client(self):
        form = ClientForm()
        if form.exec() == form.accepted:
            self.load_clients()
