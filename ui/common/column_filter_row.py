from peewee import Field
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QTableView
from PySide6.QtCore import Signal, QTimer, Qt

class ColumnFilterRow(QWidget):
    """Строка фильтров по столбцам таблицы."""

    filter_changed = Signal(int, str)

    def __init__(self, parent=None, *, linked_view: QTableView | None = None):
        super().__init__(parent)
        self._editors = []
        self._timers = []
        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(3)

        # Important: let clicks pass through empty areas of the filter row
        # so they don't block selecting rows in the table behind.
        # Editors themselves still receive events normally.
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        if linked_view is not None:
            scroll = linked_view.horizontalScrollBar()
            scroll.valueChanged.connect(self.sync_scroll)
            # синхронизируем позицию при инициализации
            self.sync_scroll(scroll.value())

    def set_headers(
        self,
        headers: list[str],
        texts: list[str] | None = None,
        column_field_map: dict[int, Field | None] | None = None,
    ):
        """Создаёт по одному полю ввода на каждый столбец.

        ``column_field_map`` позволяет скрывать фильтры для некоторых колонок,
        если в словаре указано ``None``.
        """
        # очистка старых редакторов и таймеров
        for e in self._editors:
            e.deleteLater()
        self._editors.clear()
        for t in self._timers:
            t.stop()
            t.deleteLater()
        self._timers.clear()
        while self.layout().count():
            item = self.layout().takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not headers:
            return
        for idx, h in enumerate(headers):
            le = QLineEdit(self)
            le.setPlaceholderText(str(h))

            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(300)
            timer.timeout.connect(
                lambda col=idx, editor=le: self.filter_changed.emit(
                    col, editor.text()
                )
            )
            le.textChanged.connect(lambda _text, t=timer: t.start())

            if column_field_map and column_field_map.get(idx) is None:
                le.setVisible(False)
            self.layout().addWidget(le)
            self._editors.append(le)
            self._timers.append(timer)
            if texts and idx < len(texts):
                le.blockSignals(True)
                le.setText(texts[idx])
                le.blockSignals(False)
        self.layout().addStretch()
        # ensure the filter row reserves space so it doesn't overlap table rows
        self.setFixedHeight(self.sizeHint().height())

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

    def get_all_texts(self) -> list[str]:
        """Возвращает список текущих текстов всех полей фильтра."""
        return [self.get_text(i) for i in range(len(self._editors))]

    def set_all_texts(self, texts: list[str]) -> None:
        """Устанавливает тексты для всех полей фильтра.

        Сигналы временно блокируются, чтобы не запускать фильтрацию
        при восстановлении сохранённых значений.
        """
        for idx, editor in enumerate(self._editors):
            editor.blockSignals(True)
            editor.setText(texts[idx] if idx < len(texts) else "")
            editor.blockSignals(False)

    def set_editor_visible(self, index: int, visible: bool) -> None:
        """Управляет видимостью поля фильтра по его индексу."""
        if 0 <= index < len(self._editors):
            self._editors[index].setVisible(visible)

    def clear_all(self) -> None:
        """Очищает все редакторы без генерации сигналов."""
        for editor, timer in zip(self._editors, self._timers):
            timer.stop()
            editor.blockSignals(True)
            editor.clear()
            editor.blockSignals(False)
