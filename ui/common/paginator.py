from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel


class Paginator(QWidget):
    def __init__(self, on_next=None, on_prev=None, parent=None):
        super().__init__(parent)
        self.on_next = on_next
        self.on_prev = on_prev
        self.current_page = 1

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.prev_btn = QPushButton("⬅️ Назад")
        self.prev_btn.clicked.connect(self.prev_clicked)
        layout.addWidget(self.prev_btn)

        self.page_label = QLabel("Страница 1")
        layout.addWidget(self.page_label)

        self.next_btn = QPushButton("➡️ Вперёд")
        self.next_btn.clicked.connect(self.next_clicked)
        layout.addWidget(self.next_btn)

        layout.addStretch()

    def update(self, count: int, page: int):
        self.current_page = page
        self.page_label.setText(f"Страница {page} ({count} записей)")
        self.prev_btn.setEnabled(page > 1)
        self.next_btn.setEnabled(count > 0)

    def update_page(self, page: int):
        """Для старых вьюшек"""
        self.update(count=1, page=page)

    def next_clicked(self):
        if self.on_next:
            self.on_next()

    def prev_clicked(self):
        if self.on_prev:
            self.on_prev()
