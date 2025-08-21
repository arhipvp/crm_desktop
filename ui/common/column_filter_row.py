from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit
from PySide6.QtCore import Signal

class ColumnFilterRow(QWidget):
    """Строка фильтров по столбцам таблицы."""

    filter_changed = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editors = []
        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(3)

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

    def get_text(self, column: int) -> str:
        if 0 <= column < len(self._editors):
            return self._editors[column].text().strip()
        return ""

    def set_text(self, column: int, text: str) -> None:
        if 0 <= column < len(self._editors):
            self._editors[column].setText(text)

    def get_all_texts(self) -> list[str]:
        """Возвращает список текстов всех полей фильтра."""
        return [e.text().strip() for e in self._editors]

    def set_all_texts(self, texts: list[str]) -> None:
        """Устанавливает тексты для всех полей фильтра."""
        for idx, editor in enumerate(self._editors):
            editor.blockSignals(True)
            editor.setText(texts[idx] if idx < len(texts) else "")
            editor.blockSignals(False)
