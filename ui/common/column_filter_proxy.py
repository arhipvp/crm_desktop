from PySide6.QtCore import QSortFilterProxyModel, QRegularExpression


class ColumnFilterProxyModel(QSortFilterProxyModel):
    """Простая прокси-модель с текстовыми фильтрами по столбцам."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filters: dict[int, QRegularExpression] = {}

    def set_filter(self, column: int, text: str) -> None:
        """Устанавливает фильтр для указанного столбца."""
        if text:
            self._filters[column] = QRegularExpression(
                text, QRegularExpression.PatternOption.CaseInsensitiveOption
            )
        else:
            self._filters.pop(column, None)
        self.invalidateFilter()

    def clear_filters(self) -> None:
        """Сбрасывает все фильтры."""
        self._filters.clear()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):  # noqa: N802
        for col, regex in self._filters.items():
            index = self.sourceModel().index(source_row, col, source_parent)
            data = str(self.sourceModel().data(index))
            if not regex.match(data).hasMatch():
                return False
        return True
