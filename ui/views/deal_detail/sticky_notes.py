from __future__ import annotations

from typing import Iterable, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
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

        self._archive_toggle = QCheckBox("Показать архив")
        self._archive_toggle.setChecked(False)
        self._archive_toggle.toggled.connect(lambda _: self._rebuild())
        layout.addWidget(self._archive_toggle, alignment=Qt.AlignLeft)

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

        self._active_entries: list[JournalEntry] = []
        self._archived_entries: list[JournalEntry] = []
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def load_entries(self, deal) -> None:
        """Загружает активные записи для указанной сделки."""

        active, archived = deal_journal.load_entries(deal)
        self.set_entries(active, archived)

    def set_entries(
        self,
        active_entries: Iterable[JournalEntry],
        archived_entries: Iterable[JournalEntry] | None = None,
    ) -> None:
        self._active_entries = list(active_entries)
        self._archived_entries = list(archived_entries or [])

        if self._archived_entries:
            self._archive_toggle.setEnabled(True)
        else:
            # не даём включить архив, если записей нет
            self._archive_toggle.blockSignals(True)
            self._archive_toggle.setChecked(False)
            self._archive_toggle.blockSignals(False)
            self._archive_toggle.setEnabled(False)

        self._rebuild()

    def _rebuild(self) -> None:
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        show_archive = self._archive_toggle.isChecked() and bool(
            self._archived_entries
        )

        sections: list[tuple[str | None, Sequence[JournalEntry]]] = []
        if show_archive:
            sections.append(("Активные", self._active_entries))
            sections.append(("Архив", self._archived_entries))
        else:
            sections.append((None, self._active_entries))

        has_cards = False
        for title, entries in sections:
            if title:
                header = QLabel(title)
                header.setStyleSheet("font-weight: bold; color: #444;")
                self._container_layout.addWidget(header)

            if entries:
                for entry in entries:
                    card = self._create_card(entry)
                    self._container_layout.addWidget(card)
                    has_cards = True
            else:
                placeholder_text = "Журнал пуст"
                if show_archive and title == "Активные":
                    placeholder_text = "Нет активных записей"
                elif show_archive and title == "Архив":
                    placeholder_text = "Архив пуст"
                elif not show_archive:
                    placeholder_text = "Нет активных записей"

                placeholder = QLabel(placeholder_text)
                placeholder.setAlignment(Qt.AlignCenter)
                placeholder.setStyleSheet("color: #888; font-style: italic;")
                placeholder.setTextInteractionFlags(Qt.TextSelectableByMouse)
                self._container_layout.addWidget(placeholder)

        if not has_cards and not show_archive and not self._active_entries:
            # в случае полного отсутствия записей добавляем stretch, чтобы текст был по центру
            self._container_layout.addStretch()
            return

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
