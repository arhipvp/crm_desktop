from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services import deal_journal
from services.deal_journal import JournalEntry
from ui.common.styled_widgets import styled_button


class StickyNotesBoard(QWidget):
    """Виджет для отображения активных записей журнала сделки."""

    archive_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self._scroll)

        self._container = QWidget()
        self._container.setObjectName("stickyNotesContainer")
        self._scroll.setWidget(self._container)

        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(8)

        self._entries: list[JournalEntry] = []
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def load_entries(self, deal) -> None:
        """Загружает активные записи для указанной сделки."""

        active, _ = deal_journal.load_entries(deal)
        self.set_entries(active)

    def set_entries(self, entries: Iterable[JournalEntry]) -> None:
        self._entries = list(entries)
        self._rebuild()

    def _rebuild(self) -> None:
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not self._entries:
            placeholder = QLabel("Журнал пуст")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("color: #888; font-style: italic;")
            placeholder.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._container_layout.addWidget(placeholder)
            self._container_layout.addStretch()
            return

        for entry in self._entries:
            card = self._create_card(entry)
            self._container_layout.addWidget(card)
        self._container_layout.addStretch()

    def _create_card(self, entry: JournalEntry) -> QWidget:
        card = QFrame()
        card.setObjectName("stickyCard")
        card.setStyleSheet(
            """
            QFrame#stickyCard {
                background-color: #fff9c4;
                border: 1px solid #f0e68c;
                border-radius: 6px;
            }
            """
        )
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        header = QLabel(entry.header or "—")
        header.setWordWrap(True)
        header.setStyleSheet("font-weight: bold;")
        header.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(header)

        if entry.body:
            body = QLabel(entry.body)
            body.setTextFormat(Qt.PlainText)
            body.setWordWrap(True)
            body.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(body)

        button_row = QHBoxLayout()
        button_row.addStretch()
        archive_btn: QPushButton = styled_button("В архив")
        archive_btn.clicked.connect(lambda _=False, eid=entry.entry_id: self.archive_requested.emit(eid))
        button_row.addWidget(archive_btn)
        layout.addLayout(button_row)

        return card
