from __future__ import annotations

from typing import List

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QSizePolicy, QStyle, QWidget


class MasonryLayout(QLayout):
    """Компоновщик, раскладывающий элементы по принципу «кирпичной кладки».

    Виджеты располагаются в несколько колонок. Для каждого обычного элемента
    выбирается колонка с минимальной текущей высотой, чтобы сформировать
    сбалансированную сетку. Элементы с флагом ``flow_fill_row=True`` растягиваются
    на всю ширину и начинаются с новой строки.
    """

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

    # --- Реализация абстрактных методов QLayout ---------------------------------
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

    def _bounded_item_width(self, item: QLayoutItem, target_width: int) -> int:
        width = max(target_width, 0)
        minimum = item.minimumSize().width()
        maximum = item.maximumSize().width()

        if minimum > 0:
            width = max(width, minimum)
        if 0 < maximum < width:
            width = maximum
        return width

    def _item_height_for_width(self, item: QLayoutItem, width: int) -> int:
        if item.hasHeightForWidth():
            return item.heightForWidth(width)
        hint = item.sizeHint()
        return hint.height()

    def _calculate_columns(self, available_width: int, h_space: int) -> tuple[int, int]:
        normal_items = [
            item
            for item in self._items
            if not item.isEmpty() and not self._item_fills_row(item)
        ]

        if available_width <= 0:
            return 1, 0

        if not normal_items:
            return 1, available_width

        preferred_width = max(
            max(item.sizeHint().width(), item.minimumSize().width()) or 1
            for item in normal_items
        )

        denominator = preferred_width + h_space
        if denominator <= 0:
            return 1, available_width

        columns = max(1, int((available_width + h_space) // denominator))
        columns = min(columns, len(normal_items)) or 1

        column_width = available_width - (columns - 1) * h_space
        if columns > 0:
            column_width //= columns
        else:
            column_width = available_width

        return max(columns, 1), max(column_width, 0)

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective_rect = rect.adjusted(
            margins.left(),
            margins.top(),
            -margins.right(),
            -margins.bottom(),
        )

        h_space = self.horizontalSpacing()
        v_space = self.verticalSpacing()

        available_width = max(0, effective_rect.width())
        column_count, column_width = self._calculate_columns(available_width, h_space)
        column_heights = [0] * column_count

        for item in self._items:
            if item.isEmpty():
                continue

            fills_row = self._item_fills_row(item)

            if fills_row:
                y = max(column_heights) if column_heights else 0
                item_width = available_width
                item_height = self._item_height_for_width(item, item_width)
                if not test_only:
                    item.setGeometry(
                        QRect(
                            effective_rect.x(),
                            effective_rect.y() + y,
                            item_width,
                            item_height,
                        )
                    )

                new_height = y + item_height + v_space
                for index in range(len(column_heights)):
                    column_heights[index] = new_height
                if not column_heights:
                    column_heights.append(new_height)
                continue

            if not column_heights:
                column_heights = [0]
                column_count = 1

            column_index = min(range(len(column_heights)), key=column_heights.__getitem__)
            column_x = effective_rect.x() + column_index * (column_width + h_space)

            bounded_width = self._bounded_item_width(item, column_width)
            if bounded_width > column_width:
                offset = 0
            else:
                offset = (column_width - bounded_width) // 2
            column_x += offset

            item_height = self._item_height_for_width(item, bounded_width)

            if not test_only:
                item.setGeometry(
                    QRect(
                        column_x,
                        effective_rect.y() + column_heights[column_index],
                        bounded_width,
                        item_height,
                    )
                )

            column_heights[column_index] += item_height + v_space

        total_height = max(column_heights, default=0)
        if total_height > 0:
            total_height -= v_space
        total_height = max(total_height, 0)
        total_height += margins.top() + margins.bottom()
        return total_height
