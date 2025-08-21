from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QTableView
from PySide6.QtCore import Signal

class ColumnFilterRow(QWidget):
    """Строка фильтров по столбцам таблицы."""

    filter_changed = Signal(int, str)

    def __init__(self, parent=None, *, linked_view: QTableView | None = None):
        super().__init__(parent)
        self._editors = []
        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(3)

        if linked_view is not None:
            scroll = linked_view.horizontalScrollBar()
            scroll.valueChanged.connect(self.sync_scroll)
            # синхронизируем позицию при инициализации
            self.sync_scroll(scroll.value())

    def set_headers(self, headers: list[str], texts: list[str] | None = None):
        """Создаёт по одному полю ввода на каждый столбец."""
        # очистка старых редакторов
        for e in self._editors:
            e.deleteLater()
        self._editors.clear()
        while self.layout().count():
            item = self.layout().takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not headers:
            return
        for idx, h in enumerate(headers):
            le = QLineEdit(self)
            le.setPlaceholderText(str(h))
            le.textChanged.connect(lambda text, col=idx: self.filter_changed.emit(col, text))
            self.layout().addWidget(le)
            self._editors.append(le)
            if texts and idx < len(texts):
                le.blockSignals(True)
                le.setText(texts[idx])
                le.blockSignals(False)
        self.layout().addStretch()

    def sync_scroll(self, offset: int) -> None:
        """Сдвигает строку фильтров при прокрутке связанной таблицы."""
        self.layout().setContentsMargins(-offset, 0, 0, 0)

    def get_text(self, column: int) -> str:
        if 0 <= column < len(self._editors):
            return self._editors[column].text().strip()
        return ""

    def set_text(self, column: int, text: str) -> None:
        if 0 <= column < len(self._editors):
            self._editors[column].setText(text)
