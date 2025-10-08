from collections.abc import Iterable

from PySide6.QtWidgets import QLabel, QWidget

from ui.widgets.flow_layout import FlowLayout


class ActionGroupWidget(QWidget):
    """Группа действий с заголовком и потоковой раскладкой кнопок."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = FlowLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._layout = layout
        self.setLayout(layout)

        title_label = QLabel(title, self)
        title_label.setProperty("flow_fill_row", True)
        layout.addWidget(title_label)
        self._title_label = title_label

    @property
    def title(self) -> str:
        return self._title_label.text()

    def set_title(self, title: str) -> None:
        self._title_label.setText(title)

    def add_action(self, widget: QWidget) -> None:
        """Добавить новый виджет действия."""
        self._layout.addWidget(widget)

    def set_actions(self, widgets: Iterable[QWidget]) -> None:
        """Полностью заменить набор действий."""
        self.clear_actions()
        for widget in widgets:
            self.add_action(widget)

    def clear_actions(self) -> None:
        """Удалить все действия, кроме заголовка."""
        while self._layout.count() > 1:
            item = self._layout.takeAt(1)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def action_widgets(self) -> list[QWidget]:
        """Получить текущие виджеты действий."""
        widgets: list[QWidget] = []
        for idx in range(1, self._layout.count()):
            item = self._layout.itemAt(idx)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widgets.append(widget)
        return widgets
