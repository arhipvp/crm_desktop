from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QModelIndex, Qt, QUrl
from PySide6.QtGui import (
    QAction,
    QDesktopServices,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileSystemModel,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedLayout,
    QTreeView,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class DealFilesTreeView(QTreeView):
    """Расширенный QTreeView с поддержкой DnD и защитой корневой папки."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._root_path: Path | None = None

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setAllColumnsShowFocus(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)

    def set_root_path(self, path: str | None) -> None:
        self._root_path = Path(path) if path else None

    # --- DnD helpers -------------------------------------------------
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 (Qt style)
        if self._is_dragging_root(event):
            event.ignore()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        if self._is_dragging_root(event):
            event.ignore()
            return
        action = self._resolve_drop_action(event)
        event.setDropAction(action)
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        if self._is_dragging_root(event):
            event.ignore()
            return
        action = self._resolve_drop_action(event)
        event.setDropAction(action)
        super().dropEvent(event)

    def startDrag(self, supported_actions: Qt.DropActions) -> None:  # noqa: N802
        index = self.currentIndex()
        if index.isValid() and self._is_root_index(index):
            return
        super().startDrag(supported_actions)

    # --- Internal helpers -------------------------------------------
    def _is_dragging_root(self, event: QDragEnterEvent | QDragMoveEvent | QDropEvent) -> bool:
        if not self._root_path or not event.mimeData():
            return False

        for url in event.mimeData().urls():
            if url.isLocalFile() and Path(url.toLocalFile()) == self._root_path:
                return True
        return False

    def _is_root_index(self, index: QModelIndex) -> bool:
        if not index.isValid() or not self._root_path:
            return False

        model = self.model()
        if not isinstance(model, QFileSystemModel):
            return False

        return Path(model.filePath(index)) == self._root_path

    def _resolve_drop_action(
        self, event: QDragEnterEvent | QDragMoveEvent | QDropEvent
    ) -> Qt.DropAction:
        modifiers = event.keyboardModifiers()
        possible_actions = event.possibleActions()

        if modifiers & Qt.ControlModifier and possible_actions & Qt.CopyAction:
            return Qt.CopyAction

        source = event.source()
        if source is self and possible_actions & Qt.MoveAction:
            return Qt.MoveAction

        return event.proposedAction()

from services.folder_utils import create_directory, delete_path, open_folder, rename_path


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
        self._model.setReadOnly(False)

        self._tree = DealFilesTreeView()
        self._tree.setModel(self._model)
        self._tree.setSortingEnabled(True)
        header = self._tree.header()
        if header is not None:
            header.setSectionsClickable(True)
            header.setSortIndicatorShown(True)
        self._tree.sortByColumn(0, Qt.AscendingOrder)
        self._tree.setHeaderHidden(False)
        self._tree.hide()
        self._tree.setEditTriggers(
            QAbstractItemView.EditKeyPressed | QAbstractItemView.SelectedClicked
        )
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.doubleClicked.connect(self._on_open_selected)

        self._create_action = QAction("Создать папку", self)
        self._create_action.setShortcut(QKeySequence(Qt.CTRL | Qt.SHIFT | Qt.Key_N))
        self._create_action.triggered.connect(self._on_create_folder)

        self._rename_action = QAction("Переименовать", self)
        self._rename_action.setShortcut(QKeySequence(Qt.Key_F2))
        self._rename_action.triggered.connect(self._on_rename_selected)

        self._delete_action = QAction("Удалить", self)
        self._delete_action.setShortcut(QKeySequence(Qt.Key_Delete))
        self._delete_action.triggered.connect(self._on_delete_selected)

        self._open_action = QAction("Открыть", self)
        self._open_action.setShortcuts(
            [QKeySequence(Qt.Key_Return), QKeySequence(Qt.Key_Enter)]
        )
        self._open_action.triggered.connect(self._on_open_selected)

        for action in (
            self._open_action,
            self._create_action,
            self._rename_action,
            self._delete_action,
        ):
            self._tree.addAction(action)

        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.addAction(self._create_action)
        toolbar.addAction(self._rename_action)
        toolbar.addAction(self._delete_action)
        toolbar.addSeparator()
        toolbar.addAction(self._open_action)
        self._toolbar = toolbar

        selection_model = self._tree.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(self._on_selection_changed)
            selection_model.currentChanged.connect(self._on_current_changed)

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
        content_layout.addWidget(toolbar)
        content_layout.addLayout(stack)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(6)

        self.setContentLayout(content_layout)

        self.set_folder(None)
        self._update_actions_state()

    def set_folder(self, path: str | None) -> None:
        """Обновить корневую папку дерева файлов."""

        self._folder_path = path or None

        if self._folder_path and Path(self._folder_path).is_dir():
            index = self._model.setRootPath(self._folder_path)
            self._tree.set_root_path(self._folder_path)
            self._tree.setRootIndex(index)
            selection_model = self._tree.selectionModel()
            if selection_model is not None:
                selection_model.setCurrentIndex(
                    index, QItemSelectionModel.ClearAndSelect
                )
            self._path_label.setText(self._folder_path)
            self._open_button.setEnabled(True)
            self._stack.setCurrentWidget(self._tree)
            self._tree.show()
        else:
            self._model.setRootPath("")
            self._tree.set_root_path(None)
            self._path_label.setText("Папка не выбрана")
            self._open_button.setEnabled(False)
            self._stack.setCurrentWidget(self._placeholder)
            selection_model = self._tree.selectionModel()
            if selection_model is not None:
                selection_model.clear()

        self._update_actions_state()

    def _on_open_folder(self) -> None:
        if not self._folder_path:
            return

        open_folder(self._folder_path, parent=self)

    def _on_open_selected(self, index: QModelIndex | None = None) -> None:
        if not isinstance(index, QModelIndex):
            index = None

        if index is not None and index.isValid():
            path = Path(self._model.filePath(index))
        else:
            path = self._current_selection_path()
        if path is None:
            return

        if path.is_file():
            try:
                if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                    raise RuntimeError("Не удалось открыть файл системным приложением.")
            except Exception as error:
                QMessageBox.critical(
                    self,
                    "Открытие файла",
                    f"Не удалось открыть файл '{path.name}':\n{error}",
                )
            return

        target = path if path.is_dir() else path.parent
        if target is None:
            return

        open_folder(str(target), parent=self)

    def _on_create_folder(self) -> None:
        base_dir = self._target_directory_for_creation()
        if base_dir is None:
            return

        name, accepted = QInputDialog.getText(
            self, "Создать папку", "Название новой папки:"
        )
        if not accepted:
            return

        new_name = name.strip()
        if not new_name:
            QMessageBox.warning(self, "Создание папки", "Имя не может быть пустым.")
            return

        created = create_directory(base_dir / new_name, parent=self)
        if created is None:
            return

        self._refresh_model(created)

    def _on_rename_selected(self) -> None:
        path = self._current_selection_path()
        if path is None or self._is_root_path(path):
            return

        new_name, accepted = QInputDialog.getText(
            self, "Переименовать", "Новое имя:", text=path.name
        )
        if not accepted:
            return

        renamed = rename_path(path, new_name, parent=self)
        if renamed is None:
            return

        self._refresh_model(renamed)

    def _on_delete_selected(self) -> None:
        path = self._current_selection_path()
        if path is None or self._is_root_path(path):
            return

        answer = QMessageBox.question(
            self,
            "Удаление",
            f"Удалить '{path.name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        if delete_path(path, parent=self):
            self._refresh_model(path.parent if path.parent.exists() else None)

    def _on_context_menu(self, point) -> None:
        self._update_actions_state()
        menu = QMenu(self)
        menu.addAction(self._open_action)
        menu.addSeparator()
        menu.addAction(self._create_action)
        menu.addAction(self._rename_action)
        menu.addAction(self._delete_action)
        menu.exec(self._tree.viewport().mapToGlobal(point))

    def _on_selection_changed(self, _selected, _deselected) -> None:
        self._update_actions_state()

    def _on_current_changed(self, _current: QModelIndex, _previous: QModelIndex) -> None:
        self._update_actions_state()

    def _current_selection_path(self) -> Path | None:
        index = self._tree.currentIndex()
        if index.isValid():
            return Path(self._model.filePath(index))

        if self._folder_path:
            root_path = Path(self._folder_path)
            if root_path.exists():
                return root_path

        return None

    def _target_directory_for_creation(self) -> Path | None:
        path = self._current_selection_path()
        if path is None:
            return None

        return path if path.is_dir() else path.parent

    def _refresh_model(self, focus_path: Path | None) -> None:
        if not self._folder_path:
            return

        self._model.refresh(self._tree.rootIndex())

        if focus_path is not None:
            index = self._model.index(str(focus_path))
            if index.isValid():
                self._tree.setCurrentIndex(index)
                self._tree.scrollTo(index)

        self._update_actions_state()

    def _is_root_path(self, path: Path) -> bool:
        return bool(self._folder_path) and Path(self._folder_path) == path

    def _update_actions_state(self) -> None:
        has_root = bool(self._folder_path)
        path = self._current_selection_path()
        is_valid = path is not None and path.exists()
        is_root = bool(path and self._is_root_path(path))

        self._create_action.setEnabled(has_root)
        self._open_action.setEnabled(is_valid)
        self._rename_action.setEnabled(is_valid and not is_root)
        self._delete_action.setEnabled(is_valid and not is_root)
