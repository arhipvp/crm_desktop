from PySide6.QtCore import QSortFilterProxyModel, QRegularExpression


class MultiFilterProxyModel(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self._filters: dict[int, QRegularExpression] = {}

    def set_filter(self, column: int, text: str) -> None:
        if text:
            pattern = QRegularExpression.escape(text)
            self._filters[column] = QRegularExpression(
                f".*{pattern}.*",
                QRegularExpression.PatternOption.CaseInsensitiveOption,
            )
        else:
            self._filters.pop(column, None)
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):  # noqa: N802
        for col, regex in self._filters.items():
            index = self.sourceModel().index(source_row, col, source_parent)
            data = str(self.sourceModel().data(index))
            if regex and not regex.match(data).hasMatch():
                return False
        return True
