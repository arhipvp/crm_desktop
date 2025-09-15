from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QPainter, QPolygon
from PySide6.QtWidgets import QHeaderView, QLineEdit, QMenu, QWidgetAction


class FilterHeaderView(QHeaderView):
    """Заголовок таблицы с быстрыми фильтрами."""

    filter_changed = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self._filters: dict[int, str] = {}
        self._menu: QMenu | None = None
        self._icon_rects: dict[int, QRect] = {}

    def paintSection(self, painter: QPainter, rect: QRect, index: int) -> None:  # noqa: N802
        super().paintSection(painter, rect, index)
        size = min(12, rect.height() - 4)
        icon_rect = QRect(rect.right() - size - 4, rect.center().y() - size // 2, size, size)
        self._icon_rects[index] = icon_rect
        color = Qt.red if index in self._filters else Qt.black
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        points = [
            QPoint(icon_rect.left(), icon_rect.top()),
            QPoint(icon_rect.right(), icon_rect.top()),
            QPoint(icon_rect.center().x(), icon_rect.bottom()),
        ]
        painter.drawPolygon(QPolygon(points))
        painter.restore()

    def mousePressEvent(self, event):  # noqa: N802
        column = self.logicalIndexAt(event.pos())
        if event.button() == Qt.LeftButton and column >= 0:
            icon_rect = self._icon_rects.get(column)
            if icon_rect and icon_rect.contains(event.pos()):
                self._show_editor(column)
                event.accept()
                return
        if event.button() == Qt.RightButton and column >= 0:
            self._show_editor(column)
            event.accept()
            return
        super().mousePressEvent(event)

    def _show_editor(self, column: int) -> None:
        menu = QMenu(self)
        line = QLineEdit(menu)
        line.setPlaceholderText(str(self.model().headerData(column, Qt.Horizontal)))
        line.setText(self._filters.get(column, ""))
        action = QWidgetAction(menu)
        action.setDefaultWidget(line)
        menu.addAction(action)
        line.textChanged.connect(lambda text, c=column: self._on_text_changed(c, text))
        menu.addSeparator()
        clear_action = menu.addAction("Очистить фильтр")
        clear_action.triggered.connect(lambda c=column: self._on_text_changed(c, ""))
        rect = self.sectionRect(column)
        menu.popup(self.mapToGlobal(rect.bottomLeft()))
        self._menu = menu

    def _on_text_changed(self, column: int, text: str) -> None:
        text = text.strip()
        if text:
            self._filters[column] = text
        else:
            self._filters.pop(column, None)
        self.filter_changed.emit(column, text)
        self.updateSection(column)

    # --- API для работы с фильтрами --------------------------------------
    def get_filter_text(self, column: int) -> str:
        return self._filters.get(column, "")

    def set_filter_text(self, column: int, text: str) -> None:
        self._on_text_changed(column, text)

    def get_all_filters(self) -> dict[int, str]:
        return dict(self._filters)

    def set_all_filters(self, filters: dict[int, str]) -> None:
        old_cols = set(self._filters.keys())
        self._filters = {int(k): v for k, v in filters.items() if v}
        for col in old_cols - set(self._filters.keys()):
            self.filter_changed.emit(col, "")
        for col, text in self._filters.items():
            self.filter_changed.emit(col, text)
        self.update()
