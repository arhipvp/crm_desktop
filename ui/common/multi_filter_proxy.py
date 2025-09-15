from __future__ import annotations

"""Прокси‑модель с поддержкой фильтрации по нескольким колонкам."""

from typing import Dict

from PySide6.QtCore import (
    QRegularExpression,
    Qt,
    QSortFilterProxyModel,
)


class MultiFilterProxyModel(QSortFilterProxyModel):
    """Расширенная `QSortFilterProxyModel` с несколькими фильтрами.

    Позволяет задавать отдельный текстовый фильтр для каждой колонки.
    Фильтрация выполняется по всем активным фильтрам одновременно.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._filters: Dict[int, QRegularExpression] = {}
        self._filter_strings: Dict[int, str] = {}

    def set_filter(self, column: int, text: str) -> None:
        """Устанавливает фильтр для указанной колонки.

        Пустая строка удаляет фильтр.
        """

        previous_text = self._filter_strings.get(column)
        text = text.strip()
        if text:
            options = (
                QRegularExpression.CaseInsensitiveOption
                if self.filterCaseSensitivity() == Qt.CaseInsensitive
                else QRegularExpression.NoPatternOption
            )
            esc = QRegularExpression.escape(text)
            pattern = f".*{esc}.*"
            self._filters[column] = QRegularExpression(pattern, options)
            self._filter_strings[column] = text
        else:
            self._filters.pop(column, None)
            self._filter_strings.pop(column, None)
        if previous_text != self._filter_strings.get(column):
            self.headerDataChanged.emit(Qt.Horizontal, column, column)
        self.invalidateFilter()

    # ------------------------------------------------------------------
    # QSortFilterProxyModel interface
    # ------------------------------------------------------------------
    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:  # type: ignore[override]
        model = self.sourceModel()
        if not model:
            return True
        for column, regex in self._filters.items():
            index = model.index(source_row, column, source_parent)
            data = model.data(index, self.filterRole())
            value = "" if data is None else str(data)
            if not regex.match(value).hasMatch():
                return False
        return True

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # type: ignore[override]
        value = super().headerData(section, orientation, role)
        if orientation != Qt.Horizontal:
            return value
        if role == Qt.DisplayRole and section in self._filter_strings:
            base = "" if value is None else str(value)
            if base:
                return f"{base} ⏷"
            return "⏷"
        if role == Qt.ToolTipRole and section in self._filter_strings:
            base = value
            if not base:
                base = super().headerData(section, orientation, Qt.DisplayRole)
            filter_text = self._filter_strings.get(section, "")
            if base:
                return f"{base}\nФильтр: {filter_text}"
            return f"Фильтр: {filter_text}"
        return value

