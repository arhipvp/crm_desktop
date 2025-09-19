from __future__ import annotations

import html
import re
from typing import Iterable, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from services import deal_journal
from ui.widgets.flow_layout import FlowLayout
from services.deal_journal import JournalEntry


class StickyNotesBoard(QWidget):
    """Виджет для отображения активных записей журнала сделки."""

    archive_requested = Signal(str)
    restore_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Поиск заметок…")
        self._search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search_input)

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

        self._container_layout = FlowLayout()
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(12)
        self._container.setLayout(self._container_layout)

        self._all_entries: list[tuple[bool, JournalEntry]] = []
        self._entries: list[tuple[bool, JournalEntry]] = []
        self._active_entries: list[tuple[bool, JournalEntry]] = []
        self._archived_entries: list[tuple[bool, JournalEntry]] = []
        self._search_term: str = ""
        self._card_width = 160
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def load_entries(self, deal) -> None:
        """Загружает активные записи для указанной сделки."""

        active, archived = deal_journal.load_entries(deal)
        self._search_input.blockSignals(True)
        self._search_input.clear()
        self._search_input.blockSignals(False)
        self._search_term = ""
        self.set_entries(active, archived)

    def set_entries(
        self,
        active_entries: Iterable[JournalEntry],
        archived_entries: Iterable[JournalEntry] | None = None,
    ) -> None:
        active_list = [(False, entry) for entry in active_entries]
        archived_list = [(True, entry) for entry in (archived_entries or [])]
        self._all_entries = [*active_list, *archived_list]

        self._apply_filter()

    def _rebuild(self) -> None:
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        show_archive = self._archive_toggle.isChecked() and bool(self._archived_entries)

        sections: list[tuple[str | None, Sequence[tuple[bool, JournalEntry]]]] = []
        if show_archive:
            sections.append(("Активные", self._active_entries))
            sections.append(("Архив", self._archived_entries))
        else:
            sections.append((None, self._active_entries))

        for title, entries in sections:
            if title:
                header = QLabel(title)
                header.setStyleSheet("font-weight: bold; color: #444;")
                header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                header.setProperty("flow_fill_row", True)
                self._container_layout.addWidget(header)

            if entries:
                for is_archived, entry in entries:
                    card = self._create_card(entry, is_archived)
                    self._container_layout.addWidget(card)
            else:
                placeholder_text = "Журнал пуст"
                if self._search_term:
                    placeholder_text = "Совпадений не найдено"
                elif show_archive and title == "Активные":
                    placeholder_text = "Нет активных записей"
                elif show_archive and title == "Архив":
                    placeholder_text = "Архив пуст"
                elif not show_archive:
                    placeholder_text = "Нет активных записей"

                placeholder = QLabel(placeholder_text)
                placeholder.setAlignment(Qt.AlignCenter)
                placeholder.setStyleSheet("color: #888; font-style: italic;")
                placeholder.setTextInteractionFlags(Qt.TextSelectableByMouse)
                placeholder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                placeholder.setProperty("flow_fill_row", True)
                self._container_layout.addWidget(placeholder)

    def _create_card(self, entry: JournalEntry, is_archived: bool = False) -> QWidget:
        card = QFrame()
        card.setObjectName("stickyCard")
        card.setStyleSheet(
            """
            QFrame#stickyCard {
                background-color: #fff9c4;
                border: 1px solid #f0e68c;
                border-radius: 8px;
            }
            """
        )
        card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
        card.setFixedWidth(self._card_width)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        header = QLabel()
        header.setTextFormat(Qt.RichText)
        header.setWordWrap(True)
        header.setStyleSheet("font-weight: bold;")
        header.setTextInteractionFlags(Qt.TextSelectableByMouse)
        header.setText(self._highlight_text(entry.header or "—"))
        layout.addWidget(header)

        if entry.body:
            body = QLabel()
            body.setTextFormat(Qt.RichText)
            body.setWordWrap(True)
            body.setTextInteractionFlags(Qt.TextSelectableByMouse)
            body.setText(self._highlight_text(entry.body))
            layout.addWidget(body)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(2)
        layout.addStretch()
        button_row.addStretch()
        if is_archived:
            restore_btn = QToolButton()
            restore_btn.setObjectName("stickyRestoreButton")
            restore_btn.setText("↩")
            restore_btn.setToolTip("Восстановить из архива")
            restore_btn.setCursor(Qt.PointingHandCursor)
            restore_btn.setAutoRaise(True)
            restore_btn.setStyleSheet(
                """
                QToolButton#stickyRestoreButton {
                    border: none;
                    padding: 0;
                    font-size: 14px;
                }
                QToolButton#stickyRestoreButton:hover {
                    background-color: rgba(0, 0, 0, 0.05);
                    border-radius: 6px;
                }
                """
            )
            restore_btn.clicked.connect(
                lambda _=False, eid=entry.entry_id: self.restore_requested.emit(eid)
            )
            button_row.addWidget(restore_btn)
        else:
            archive_btn = QToolButton()
            archive_btn.setObjectName("stickyArchiveButton")
            archive_btn.setText("🗄")
            archive_btn.setToolTip("Переместить в архив")
            archive_btn.setCursor(Qt.PointingHandCursor)
            archive_btn.setAutoRaise(True)
            archive_btn.setStyleSheet(
                """
                QToolButton#stickyArchiveButton {
                    border: none;
                    padding: 0;
                    font-size: 16px;
                }
                QToolButton#stickyArchiveButton:hover {
                    background-color: rgba(0, 0, 0, 0.05);
                    border-radius: 6px;
                }
                """
            )
            archive_btn.clicked.connect(
                lambda _=False, eid=entry.entry_id: self.archive_requested.emit(eid)
            )
            button_row.addWidget(archive_btn)
        layout.addLayout(button_row)

        tooltip_parts: list[str] = []
        header_text = entry.header or "—"
        tooltip_parts.append(
            f"<b>{self._highlight_text(header_text)}</b>"
        )
        if entry.body:
            tooltip_parts.append(self._highlight_text(entry.body))
        card.setToolTip("<br/><br/>".join(tooltip_parts))
        header.setToolTip(card.toolTip())
        if entry.body:
            body.setToolTip(card.toolTip())

        return card

    def _on_search_changed(self, text: str) -> None:
        self._search_term = text.strip()
        self._apply_filter()

    def _apply_filter(self) -> None:
        term = self._search_term.lower()
        if not term:
            self._entries = list(self._all_entries)
        else:
            self._entries = [
                (is_archived, entry)
                for is_archived, entry in self._all_entries
                if term in (entry.header or "").lower()
                or term in (entry.body or "").lower()
            ]

        self._active_entries = [
            (archived, entry) for archived, entry in self._entries if not archived
        ]
        self._archived_entries = [
            (archived, entry) for archived, entry in self._entries if archived
        ]

        if self._archived_entries:
            self._archive_toggle.setEnabled(True)
        else:
            self._archive_toggle.blockSignals(True)
            self._archive_toggle.setChecked(False)
            self._archive_toggle.blockSignals(False)
            self._archive_toggle.setEnabled(False)

        self._rebuild()

    def _highlight_text(self, text: str) -> str:
        if not text:
            return ""

        if not self._search_term:
            return html.escape(text).replace("\n", "<br/>")

        pattern = re.compile(re.escape(self._search_term), re.IGNORECASE)
        parts: list[str] = []
        last_index = 0
        for match in pattern.finditer(text):
            parts.append(html.escape(text[last_index:match.start()]))
            highlighted = html.escape(match.group(0))
            parts.append(f'<span style="background-color: #ffe082;">{highlighted}</span>')
            last_index = match.end()
        parts.append(html.escape(text[last_index:]))
        return "".join(parts).replace("\n", "<br/>")
