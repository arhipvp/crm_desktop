from __future__ import annotations

from typing import Dict, List

from peewee import Field
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHeaderView, QLineEdit


class FilterHeaderView(QHeaderView):
    """Заголовок таблицы с полями фильтрации под каждой колонкой."""

    filter_changed = Signal(int, str)

    def __init__(self, parent=None) -> None:
        super().__init__(Qt.Horizontal, parent)
        self._editors: Dict[int, QLineEdit] = {}
        self._timers: Dict[int, QTimer] = {}
        self._base_height = super().sizeHint().height()
        self._editor_height = 22

        self.sectionResized.connect(self._update_editor_positions)
        self.sectionMoved.connect(self._update_editor_positions)

    # ------------------------------------------------------------------
    def set_headers(
        self,
        headers: List[str],
        texts: List[str] | None = None,
        column_field_map: Dict[int, Field | str | None] | None = None,
    ) -> None:
        for editor in self._editors.values():
            editor.deleteLater()
        for timer in self._timers.values():
            timer.stop()
            timer.deleteLater()
        self._editors.clear()
        self._timers.clear()

        for logical, h in enumerate(headers):
            le = QLineEdit(self)
            le.setPlaceholderText(str(h))

            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(300)
            timer.timeout.connect(
                lambda col=logical, editor=le: self.filter_changed.emit(
                    self.visualIndex(col), editor.text()
                )
            )
            le.textChanged.connect(lambda _text, t=timer: t.start())

            if column_field_map and column_field_map.get(logical) is None:
                le.setVisible(False)

            if texts and logical < len(texts):
                le.blockSignals(True)
                le.setText(texts[logical])
                le.blockSignals(False)

            self._editors[logical] = le
            self._timers[logical] = timer

        self._update_height()
        self._update_editor_positions()

    # ------------------------------------------------------------------
    def _update_height(self) -> None:
        self.setFixedHeight(self._base_height + self._editor_height)

    def _update_editor_positions(self) -> None:
        for logical, editor in self._editors.items():
            x = self.sectionViewportPosition(logical)
            w = self.sectionSize(logical)
            editor.setGeometry(
                x,
                self._base_height,
                w,
                self._editor_height,
            )

    def resizeEvent(self, event):  # noqa: D401 - Qt override
        super().resizeEvent(event)
        self._update_editor_positions()

    def paintSection(self, painter, rect, logicalIndex):  # noqa: N802
        rect = rect.adjusted(0, 0, 0, -self._editor_height)
        super().paintSection(painter, rect, logicalIndex)

    # ------------------------------------------------------------------
    def get_filter_text(self, visual: int) -> str:
        logical = self.logicalIndex(visual)
        editor = self._editors.get(logical)
        if editor:
            return editor.text().strip()
        return ""

    def set_filter_text(self, visual: int, text: str) -> None:
        logical = self.logicalIndex(visual)
        editor = self._editors.get(logical)
        if editor:
            editor.setText(text)

    def get_all_filters(self) -> List[str]:
        return [self.get_filter_text(v) for v in range(self.count())]

    def set_all_filters(self, texts: List[str]) -> None:
        for visual in range(self.count()):
            logical = self.logicalIndex(visual)
            editor = self._editors.get(logical)
            if editor:
                editor.blockSignals(True)
                editor.setText(texts[visual] if visual < len(texts) else "")
                editor.blockSignals(False)

    def set_editor_visible(self, logical: int, visible: bool) -> None:
        editor = self._editors.get(logical)
        if editor:
            editor.setVisible(visible)

    def clear_all(self) -> None:
        for logical, editor in self._editors.items():
            timer = self._timers.get(logical)
            if timer:
                timer.stop()
            editor.blockSignals(True)
            editor.clear()
            editor.blockSignals(False)
