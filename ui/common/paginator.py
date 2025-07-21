from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
import math


class Paginator(QWidget):
    def __init__(self, on_next=None, on_prev=None, parent=None, *, per_page: int = 30):
        super().__init__(parent)
        self.on_next = on_next
        self.on_prev = on_prev
        self.current_page = 1
        self.per_page = per_page

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

    def update(self, total_count: int, page: int, per_page: int | None = None):
        """Обновить состояние пагинатора с учётом общего числа записей."""
        if per_page is not None:
            self.per_page = per_page
        self.current_page = page
        total_pages = max(1, math.ceil(total_count / self.per_page))
        self.page_label.setText(
            f"Страница {page} из {total_pages} ({total_count} записей)"
        )
        self.prev_btn.setEnabled(page > 1)
        self.next_btn.setEnabled(page < total_pages)

    def update_page(
        self,
        page: int,
        items_count: int,
        per_page: int | None = None,
    ):
        """Обновить только текущую страницу без знания общего количества."""
        if per_page is not None:
            self.per_page = per_page
        self.current_page = page
        self.page_label.setText(f"Страница {page}")
        self.prev_btn.setEnabled(page > 1)
        self.next_btn.setEnabled(items_count >= self.per_page)

    def next_clicked(self):
        if self.on_next:
            self.on_next()

    def prev_clicked(self):
        if self.on_prev:
            self.on_prev()
