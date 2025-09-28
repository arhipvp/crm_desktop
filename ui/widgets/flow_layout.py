from __future__ import annotations

from typing import List

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QSizePolicy, QStyle, QWidget


class FlowLayout(QLayout):
    """Компоновщик, размещающий элементы последовательно по строкам."""

    def __init__(
        self,
        parent: QWidget | None = None,
        margin: int = 0,
        spacing: int = -1,
    ) -> None:
        super().__init__(parent)
        self._items: List[QLayoutItem] = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def __del__(self) -> None:  # pragma: no cover - Qt сам очищает дочерние виджеты
        while self.count():
            item = self.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget is not None and widget.parent() is None:
                widget.deleteLater()

    def addItem(self, item: QLayoutItem) -> None:  # noqa: D401 - стандарт Qt
        self._items.append(item)

    def count(self) -> int:  # noqa: D401 - стандарт Qt
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: D401 - стандарт Qt
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: D401 - стандарт Qt
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientations:  # noqa: D401 - стандарт Qt
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:  # noqa: D401 - стандарт Qt
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: D401 - стандарт Qt
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: D401 - стандарт Qt
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: D401 - стандарт Qt
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: D401 - стандарт Qt
        margins = self.contentsMargins()
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    # --- Вспомогательные методы -------------------------------------------------
    def horizontalSpacing(self) -> int:
        spacing = self.spacing()
        if spacing >= 0:
            return spacing
        return self._smart_spacing(QStyle.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self) -> int:
        spacing = self.spacing()
        if spacing >= 0:
            return spacing
        return self._smart_spacing(QStyle.PM_LayoutVerticalSpacing)

    def _smart_spacing(self, pm: QStyle.PixelMetric) -> int:
        parent = self.parent()
        if parent is None:
            return 0
        if isinstance(parent, QWidget):
            return parent.style().pixelMetric(pm, None, parent)
        return parent.spacing()

    def _item_fills_row(self, item: QLayoutItem) -> bool:
        widget = item.widget()
        if widget is None:
            return False
        fill_property = widget.property("flow_fill_row")
        if fill_property is True:
            return True
        if fill_property is False:
            return False
        policy = widget.sizePolicy().horizontalPolicy()
        return policy in (QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective_rect = rect.adjusted(
            margins.left(),
            margins.top(),
            -margins.right(),
            -margins.bottom(),
        )
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0
        right_limit = effective_rect.right()

        h_space = self.horizontalSpacing()
        v_space = self.verticalSpacing()

        for item in self._items:
            if item.isEmpty():
                continue

            size_hint = item.sizeHint()
            fills_row = self._item_fills_row(item)

            if fills_row:
                if x != effective_rect.x():
                    y += line_height + v_space
                    x = effective_rect.x()
                    line_height = 0

                item_rect = QRect(
                    QPoint(effective_rect.x(), y),
                    QSize(effective_rect.width(), size_hint.height()),
                )

                if not test_only:
                    item.setGeometry(item_rect)

                y += size_hint.height() + v_space
                x = effective_rect.x()
                line_height = 0
                continue

            next_x = x + size_hint.width()
            if x != effective_rect.x():
                next_x += h_space

            if next_x - h_space > right_limit and line_height > 0:
                y += line_height + v_space
                x = effective_rect.x()
                line_height = 0
                next_x = x + size_hint.width()

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), size_hint))

            x = next_x
            line_height = max(line_height, size_hint.height())

        total_height = y - effective_rect.y() + line_height
        total_height += margins.top() + margins.bottom()
        return total_height
