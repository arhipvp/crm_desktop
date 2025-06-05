from PySide6.QtCore import QDate, QSortFilterProxyModel, Qt

class ColumnFilterProxyModel(QSortFilterProxyModel):
    """Фильтрация по нескольким столбцам с поддержкой дат."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.column_filters: dict[int, str] = {}

    def set_filter(self, column: int, text: str):
        self.column_filters[column] = text
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        for col, pattern in self.column_filters.items():
            if not pattern:
                continue
            index = model.index(source_row, col, source_parent)
            data = str(model.data(index, Qt.DisplayRole))
            if pattern.lower() not in data.lower():
                return False
        return super().filterAcceptsRow(source_row, source_parent)

    def lessThan(self, left, right):
        left_data = self.sourceModel().data(left, Qt.UserRole)
        right_data = self.sourceModel().data(right, Qt.UserRole)
        if isinstance(left_data, QDate) and isinstance(right_data, QDate):
            return left_data < right_data
        return super().lessThan(left, right)
