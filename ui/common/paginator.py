from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
)
from PySide6.QtCore import Signal
import math


class Paginator(QWidget):
    per_page_changed = Signal(int)

    def __init__(
        self,
        on_next=None,
        on_prev=None,
        parent=None,
        *,
        per_page: int = 30,
        per_page_options: list[int] | None = None,
    ):
        super().__init__(parent)
        self.on_next = on_next
        self.on_prev = on_prev
        self.current_page = 1
        self.per_page = per_page
        self.per_page_options = per_page_options or [10, 30, 50, 100]

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

        # выбор количества на странице
        self.per_page_combo = QComboBox()
        for option in self.per_page_options:
            self.per_page_combo.addItem(str(option))
        self.per_page_combo.setCurrentText(str(self.per_page))
        self.per_page_combo.currentTextChanged.connect(self._on_per_page_changed)
        layout.addWidget(QLabel("На странице:"))
        layout.addWidget(self.per_page_combo)

        layout.addStretch()

        self.summary_label = QLabel("")
        layout.addWidget(self.summary_label)

    def update(self, total_count: int, page: int, per_page: int | None = None):
        """Обновить состояние пагинатора с учётом общего числа записей."""
        if per_page is not None:
            self.per_page = per_page
            self.per_page_combo.blockSignals(True)
            self.per_page_combo.setCurrentText(str(per_page))
            self.per_page_combo.blockSignals(False)
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
            self.per_page_combo.blockSignals(True)
            self.per_page_combo.setCurrentText(str(per_page))
            self.per_page_combo.blockSignals(False)
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

    def set_summary(self, text: str):
        self.summary_label.setText(text)

    def _on_per_page_changed(self, text: str):
        try:
            value = int(text)
        except ValueError:
            return
        if value != self.per_page:
            self.per_page = value
            self.per_page_changed.emit(value)
