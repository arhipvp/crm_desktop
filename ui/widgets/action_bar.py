from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QVBoxLayout, QWidget


class ActionBar(QWidget):
    """Панель действий, отображающая кнопки активного таба."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._current_widget: QWidget | None = None
        self.hide()

    def set_widget(self, widget: QWidget | None) -> None:
        """Устанавливает текущий контейнер действий."""
        if widget is self._current_widget:
            self._update_visibility()
            return

        if self._current_widget is not None:
            self._layout.removeWidget(self._current_widget)
            self._current_widget.hide()
            self._current_widget.setParent(None)

        self._current_widget = widget

        if widget is not None:
            previous_parent = widget.parentWidget()
            if previous_parent is not None and previous_parent is not self:
                previous_layout = previous_parent.layout()
                if previous_layout is not None:
                    previous_layout.removeWidget(widget)
            widget.setParent(self)
            self._layout.addWidget(widget)
            widget.show()

        self._update_visibility()

    def _update_visibility(self) -> None:
        self.setVisible(self._has_visible_actions())

    def _has_visible_actions(self) -> bool:
        widget = self._current_widget
        if widget is None:
            return False

        layout = widget.layout()
        if layout is None:
            return widget.isVisible()

        for index in range(layout.count()):
            child = layout.itemAt(index).widget()
            if child is not None and child.isVisible():
                return True
        return False
