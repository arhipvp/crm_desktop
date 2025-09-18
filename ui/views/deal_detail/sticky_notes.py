from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QCheckBox,
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
    show_archived_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(0, 0, 0, 0)
        controls_row.setSpacing(6)

        self._show_archived_checkbox = QCheckBox("Показывать архивные записи")
        self._show_archived_checkbox.toggled.connect(self._on_toggle_archived)
        controls_row.addWidget(self._show_archived_checkbox)
        controls_row.addStretch()
        layout.addLayout(controls_row)

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
        self._show_archived = False
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def load_entries(self, deal) -> None:
        """Загружает активные записи для указанной сделки."""

        active, archived = deal_journal.load_entries(deal)
        self._active_entries = list(active)
        self._archived_entries = list(archived)
        self._rebuild()

    def set_entries(self, entries: Iterable[JournalEntry]) -> None:
        self._active_entries = list(entries)
        self._rebuild()

    def set_show_archived(self, show: bool) -> None:
        if self._show_archived == show:
            return
        self._show_archived = show
        was_blocked = self._show_archived_checkbox.blockSignals(True)
        self._show_archived_checkbox.setChecked(show)
        self._show_archived_checkbox.blockSignals(was_blocked)
        self.show_archived_changed.emit(show)
        self._rebuild()

    def is_showing_archived(self) -> bool:
        return self._show_archived

    def _rebuild(self) -> None:
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        has_active = bool(self._active_entries)
        has_archived = bool(self._archived_entries)
        if not has_active and (not self._show_archived or not has_archived):
            placeholder = QLabel("Журнал пуст")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("color: #888; font-style: italic;")
            placeholder.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._container_layout.addWidget(placeholder)
            self._container_layout.addStretch()
            return

        for entry in self._active_entries:
            card = self._create_card(entry, archived=False)
            self._container_layout.addWidget(card)

        if self._show_archived and has_archived:
            archive_label = QLabel("Архив")
            archive_label.setAlignment(Qt.AlignLeft)
            archive_label.setStyleSheet(
                "color: #555; font-weight: bold; padding-top: 4px;"
            )
            archive_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._container_layout.addWidget(archive_label)

            for entry in self._archived_entries:
                card = self._create_card(entry, archived=True)
                self._container_layout.addWidget(card)
        self._container_layout.addStretch()

    def _on_toggle_archived(self, checked: bool) -> None:
        self.set_show_archived(checked)

    def _create_card(self, entry: JournalEntry, *, archived: bool) -> QWidget:
        card = QFrame()
        card.setObjectName("stickyCard")
        if archived:
            background = "#f5f5f5"
            border = "#dcdcdc"
        else:
            background = "#fff9c4"
            border = "#f0e68c"
        card.setStyleSheet(
            """
            QFrame#stickyCard {{
                background-color: {background};
                border: 1px solid {border};
                border-radius: 6px;
            }}
            """.format(background=background, border=border)
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

        if not archived:
            button_row = QHBoxLayout()
            button_row.addStretch()
            archive_btn: QPushButton = styled_button("В архив")
            archive_btn.clicked.connect(
                lambda _=False, eid=entry.entry_id: self.archive_requested.emit(eid)
            )
            button_row.addWidget(archive_btn)
            layout.addLayout(button_row)

        return card
