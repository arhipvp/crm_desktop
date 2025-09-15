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

    def set_filter(self, column: int, text: str) -> None:
        """Устанавливает фильтр для указанной колонки.

        Пустая строка удаляет фильтр.
        """

        text = text.strip()
        if text:
            options = (
                QRegularExpression.CaseInsensitiveOption
                if self.filterCaseSensitivity() == Qt.CaseInsensitive
                else QRegularExpression.NoPatternOption
            )
            pattern = QRegularExpression.escape(text)
            self._filters[column] = QRegularExpression(pattern, options)
        else:
            self._filters.pop(column, None)
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

