from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QCheckBox,
    QScrollArea,
)

from services.policy_service import get_policies_page
from ui.widgets.policy_card import PolicyCard
from ui.forms.policy_form import PolicyForm
from ui.common.paginator import Paginator
from ui.common.refresh_button import RefreshButton


class PolicyView(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)

        # Параметры пагинации
        self.current_page = 1
        self.per_page = 50

        # Верхняя панель управления
        control_layout = QHBoxLayout()

        self.add_btn = QPushButton("➕ Добавить полис")
        self.add_btn.clicked.connect(self.add_policy)
        control_layout.addWidget(self.add_btn)

        self.refresh_btn = RefreshButton(self.load_policies)
        control_layout.addWidget(self.refresh_btn)

        self.show_deleted_checkbox = QCheckBox("Показывать удалённые")
        self.show_deleted_checkbox.setChecked(False)
        self.show_deleted_checkbox.stateChanged.connect(self.reset_pagination)
        control_layout.addWidget(self.show_deleted_checkbox)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Поиск по номеру полиса или имени клиента..."
        )
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

        self.load_policies()

    def reset_pagination(self):
        self.current_page = 1
        self.load_policies()

    def load_policies(self):
        search_text = self.search_input.text().strip().lower()
        show_deleted = self.show_deleted_checkbox.isChecked()

        self.policies = get_policies_page(
            self.current_page, self.per_page, search_text, show_deleted
        )
        self.render_policies()
        self.paginator.update_page(
            self.current_page, len(self.policies), self.per_page
        )

    def render_policies(self):
        for i in reversed(range(self.content_layout.count())):
            widget = self.content_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        for policy in self.policies:
            card = PolicyCard(policy, parent=self)
            self.content_layout.addWidget(card)

        self.content_layout.addStretch()

    def next_page(self):
        self.current_page += 1
        self.load_policies()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_policies()

    def add_policy(self):
        form = PolicyForm()
        if form.exec() == form.Accepted:
            self.load_policies()
