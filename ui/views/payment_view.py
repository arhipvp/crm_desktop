from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QCheckBox,
    QScrollArea,
)

from services.payment_service import get_payments_page
from ui.widgets.payment_card import PaymentCard
from ui.forms.payment_form import PaymentForm
from ui.common.paginator import Paginator


class PaymentView(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)

        # Параметры пагинации
        self.current_page = 1
        self.per_page = 50

        # Верхняя панель управления
        control_layout = QHBoxLayout()

        self.add_btn = QPushButton("➕ Добавить платёж")
        self.add_btn.clicked.connect(self.add_payment)
        control_layout.addWidget(self.add_btn)

        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self.load_payments)
        control_layout.addWidget(self.refresh_btn)

        self.show_deleted_checkbox = QCheckBox("Показывать удалённые")
        self.show_deleted_checkbox.setChecked(False)
        self.show_deleted_checkbox.stateChanged.connect(self.reset_pagination)
        control_layout.addWidget(self.show_deleted_checkbox)

        self.include_paid_checkbox = QCheckBox("Показывать оплаченные")
        self.include_paid_checkbox.setChecked(True)
        self.include_paid_checkbox.stateChanged.connect(self.reset_pagination)
        control_layout.addWidget(self.include_paid_checkbox)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Поиск по номеру полиса или имени клиента..."
        )
        self.search_input.returnPressed.connect(self.reset_pagination)
        control_layout.addWidget(self.search_input)

        self.clear_search_btn = QPushButton("Очистить")
        self.clear_search_btn.clicked.connect(self.clear_search)
        control_layout.addWidget(self.clear_search_btn)

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

        self.load_payments()

    def reset_pagination(self):
        self.current_page = 1
        self.load_payments()

    def clear_search(self):
        self.search_input.clear()
        self.reset_pagination()

    def load_payments(self):
        search_text = self.search_input.text().strip().lower()
        show_deleted = self.show_deleted_checkbox.isChecked()
        include_paid = self.include_paid_checkbox.isChecked()

        self.payments = get_payments_page(
            self.current_page,
            self.per_page,
            search_text,
            show_deleted,
            include_paid=include_paid,
        )

        self.render_payments()
        self.paginator.update_page(
            self.current_page, len(self.payments), self.per_page
        )

    def render_payments(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            else:
                del item

        for payment in self.payments:
            card = PaymentCard(payment, parent=self)
            self.content_layout.addWidget(card)

        self.content_layout.addStretch()

    def next_page(self):
        self.current_page += 1
        self.load_payments()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_payments()

    def add_payment(self):
        form = PaymentForm()
        if form.exec() == form.Accepted:
            self.load_payments()
