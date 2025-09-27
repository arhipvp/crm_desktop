from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileSystemModel,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedLayout,
    QTreeView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from services.folder_utils import open_folder


class CollapsibleWidget(QWidget):
    """Простая collapsible-панель с кнопкой раскрытия."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.toggle = QToolButton(text=title, checkable=True, checked=True)
        self.toggle.setStyleSheet("QToolButton { border: none; }")
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.DownArrow)
        self.toggle.clicked.connect(self._on_toggled)

        self.content = QWidget()
        self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle)
        layout.addWidget(self.content)

    def setContentLayout(self, layout: QVBoxLayout | QFormLayout | QHBoxLayout) -> None:
        self.content.setLayout(layout)

    def _on_toggled(self, checked: bool) -> None:
        self.content.setVisible(checked)
        self.toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)


class DealFilesPanel(CollapsibleWidget):
    """Панель для отображения локальной папки сделки."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Файлы сделки", parent)

        self._folder_path: str | None = None
        self._model = QFileSystemModel(self)
        self._model.setReadOnly(True)

        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setHeaderHidden(False)
        self._tree.hide()

        self._path_label = QLabel()
        self._path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._path_label.setWordWrap(True)

        self._open_button = QPushButton("Открыть папку")
        self._open_button.clicked.connect(self._on_open_folder)

        controls = QHBoxLayout()
        controls.addWidget(self._open_button)
        controls.addWidget(self._path_label, stretch=1)

        self._placeholder = QLabel("Локальная папка не привязана.")
        self._placeholder.setAlignment(Qt.AlignCenter)

        stack = QStackedLayout()
        stack.addWidget(self._placeholder)
        stack.addWidget(self._tree)
        self._stack = stack

        content_layout = QVBoxLayout()
        content_layout.addLayout(controls)
        content_layout.addLayout(stack)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(6)

        self.setContentLayout(content_layout)

        self.set_folder(None)

    def set_folder(self, path: str | None) -> None:
        """Обновить корневую папку дерева файлов."""

        self._folder_path = path or None

        if self._folder_path and Path(self._folder_path).is_dir():
            index = self._model.setRootPath(self._folder_path)
            self._tree.setRootIndex(index)
            self._path_label.setText(self._folder_path)
            self._open_button.setEnabled(True)
            self._stack.setCurrentWidget(self._tree)
            self._tree.show()
        else:
            self._model.setRootPath("")
            self._path_label.setText("Папка не выбрана")
            self._open_button.setEnabled(False)
            self._stack.setCurrentWidget(self._placeholder)

    def _on_open_folder(self) -> None:
        if not self._folder_path:
            return

        open_folder(self._folder_path, parent=self)
