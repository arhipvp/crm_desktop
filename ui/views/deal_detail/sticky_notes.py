from __future__ import annotations

import html
import re
from typing import Iterable, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontMetrics
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
from ui.widgets.masonry_layout import MasonryLayout
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

        self._container_layout = MasonryLayout()
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(12)
        self._container.setLayout(self._container_layout)

        self._all_entries: list[tuple[bool, JournalEntry]] = []
        self._entries: list[tuple[bool, JournalEntry]] = []
        self._active_entries: list[tuple[bool, JournalEntry]] = []
        self._archived_entries: list[tuple[bool, JournalEntry]] = []
        self._search_term: str = ""
        self._card_min_width = 200
        self._card_max_width = 360
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
                header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
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
                placeholder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
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

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        header = QLabel()
        header.setTextFormat(Qt.RichText)
        header.setWordWrap(True)
        header.setStyleSheet("font-weight: bold;")
        header.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(header)

        body: QLabel | None = None
        if entry.body:
            body = QLabel()
            body.setTextFormat(Qt.RichText)
            body.setWordWrap(True)
            body.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(body)

        margins = layout.contentsMargins()
        spacing = layout.spacing()
        max_text_width = 0

        header_text = entry.header or "—"
        body_text = entry.body or ""

        header_metrics = QFontMetrics(header.font())
        header_lines = header_text.splitlines() or ["—"]
        max_text_width = max(
            max_text_width,
            max(header_metrics.horizontalAdvance(line) for line in header_lines),
        )

        if body:
            body_metrics = QFontMetrics(body.font())
            body_lines = body_text.splitlines() or [body_text]
            max_text_width = max(
                max_text_width,
                max(body_metrics.horizontalAdvance(line) for line in body_lines),
            )

        required_width = max_text_width + margins.left() + margins.right()
        if body:
            required_width += spacing

        bounded_width = max(
            self._card_min_width,
            min(self._card_max_width, required_width),
        )

        card.setMinimumWidth(int(bounded_width))
        card.setMaximumWidth(int(bounded_width))

        available_width = int(bounded_width) - (margins.left() + margins.right())
        wrapped_header = self._wrap_text(header_text, header_metrics, available_width)
        header.setText(self._highlight_text(wrapped_header))

        wrapped_body: str | None = None
        if body:
            wrapped_body = self._wrap_text(body_text, body_metrics, available_width)
            body.setText(self._highlight_text(wrapped_body))

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
        tooltip_parts.append(
            f"<b>{self._highlight_text(wrapped_header)}</b>"
        )
        if wrapped_body:
            tooltip_parts.append(self._highlight_text(wrapped_body))
        card.setToolTip("<br/><br/>".join(tooltip_parts))
        header.setToolTip(card.toolTip())
        if entry.body:
            body.setToolTip(card.toolTip())

        card.adjustSize()

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

    def _wrap_text(
        self, text: str, metrics: QFontMetrics, max_width: int
    ) -> str:
        if not text or max_width <= 0:
            return text

        soft_break = "\u200b"
        wrapped_lines: list[str] = []

        def append_line(line: str) -> None:
            if line:
                while line.endswith(soft_break):
                    line = line[:-1]
            wrapped_lines.append(line.rstrip())

        for source_line in text.split("\n"):
            if not source_line:
                wrapped_lines.append("")
                continue

            current_line = ""
            current_plain = ""
            tokens = re.split(r"(\s+)", source_line)

            for token in tokens:
                if token is None or token == "":
                    continue

                if token.isspace():
                    if not current_plain:
                        continue
                    candidate_plain = current_plain + token
                    if metrics.horizontalAdvance(candidate_plain) <= max_width:
                        current_line += token
                        current_plain = candidate_plain
                    else:
                        append_line(current_line)
                        current_line = ""
                        current_plain = ""
                    continue

                segments = self._split_word_segments(token, metrics, max_width)
                for index, segment in enumerate(segments):
                    if current_plain and metrics.horizontalAdvance(current_plain + segment) > max_width:
                        append_line(current_line)
                        current_line = ""
                        current_plain = ""

                    current_line += segment
                    current_plain += segment

                    if index < len(segments) - 1:
                        next_segment = segments[index + 1]
                        if (
                            metrics.horizontalAdvance(current_plain + next_segment)
                            <= max_width
                        ):
                            current_line += soft_break

            append_line(current_line)

        return "\n".join(wrapped_lines)

    def _split_word_segments(
        self, word: str, metrics: QFontMetrics, max_width: int
    ) -> list[str]:
        if not word:
            return [""]

        if metrics.horizontalAdvance(word) <= max_width or max_width <= 0:
            return [word]

        segments: list[str] = []
        start = 0
        length = len(word)

        while start < length:
            end = start + 1
            while end <= length and metrics.horizontalAdvance(word[start:end]) <= max_width:
                end += 1

            if end == start + 1 and metrics.horizontalAdvance(word[start:end]) > max_width:
                end = start + 1
            else:
                end -= 1

            segment = word[start:end]
            if not segment:
                segment = word[start : start + 1]
                end = start + 1

            segments.append(segment)
            start = end

        return segments

    def _highlight_text(self, text: str) -> str:
        if not text:
            return ""

        if not self._search_term:
            return self._convert_to_html(text)

        normalized_chars: list[str] = []
        for ch in text:
            if ch == "\u200b":
                continue
            if ch == "\n":
                normalized_chars.append(" ")
            else:
                normalized_chars.append(ch)

        normalized_text = "".join(normalized_chars)
        pattern = self._build_search_pattern()
        matches = list(pattern.finditer(normalized_text))

        if not matches:
            return self._convert_to_html(text)

        parts: list[str] = []
        current_match_index = 0
        current_match = matches[current_match_index]
        in_highlight = False
        plain_index = 0

        for ch in text:
            if ch == "\u200b":
                parts.append("<wbr/>")
                continue

            while current_match and plain_index >= current_match.end():
                if in_highlight:
                    parts.append("</span>")
                    in_highlight = False
                current_match_index += 1
                if current_match_index >= len(matches):
                    current_match = None
                else:
                    current_match = matches[current_match_index]

            highlight_char = False
            if current_match and current_match.start() <= plain_index < current_match.end():
                highlight_char = True

            html_fragment = "<br/>" if ch == "\n" else html.escape(ch)

            if highlight_char:
                if not in_highlight:
                    parts.append('<span style="background-color: #ffe082;">')
                    in_highlight = True
                parts.append(html_fragment)
            else:
                if in_highlight:
                    parts.append("</span>")
                    in_highlight = False
                parts.append(html_fragment)

            plain_index += 1

        if in_highlight:
            parts.append("</span>")

        return "".join(parts)

    def _convert_to_html(self, text: str) -> str:
        parts: list[str] = []
        for ch in text:
            if ch == "\u200b":
                parts.append("<wbr/>")
            elif ch == "\n":
                parts.append("<br/>")
            else:
                parts.append(html.escape(ch))
        return "".join(parts)

    def _build_search_pattern(self) -> re.Pattern[str]:
        parts: list[str] = []
        last_was_space = False
        for ch in self._search_term:
            if ch.isspace():
                if not last_was_space:
                    parts.append(r"\s+")
                    last_was_space = True
            else:
                if last_was_space:
                    last_was_space = False
                parts.append(re.escape(ch))
                parts.append(r"\s*")

        if parts and parts[-1] == r"\s*":
            parts.pop()

        pattern_str = "".join(parts) or re.escape(self._search_term)
        return re.compile(pattern_str, re.IGNORECASE)
