import base64

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui import settings as ui_settings
from ui.common.styled_widgets import styled_button
from utils.screen_utils import get_scaled_size


class BaseDetailView(QDialog):
    SETTINGS_KEY: str | None = None

    def __init__(self, instance, title=None, parent=None):
        super().__init__(parent)
        self.instance = instance
        self.setWindowTitle(title or f"{type(instance).__name__} — Подробнее")
        size = get_scaled_size(1100, 720)
        self.resize(size)
        self.setMinimumSize(800, 600)

        self.layout = QVBoxLayout(self)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.layout.addWidget(self.splitter, stretch=1)

        # ───── Левая колонка ─────
        self.left_panel = QWidget()
        self.left_panel.setMinimumWidth(260)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        title_str = self.get_title()
        self.title_label = QLabel(title_str)
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.title_label.setWordWrap(True)
        left_layout.addWidget(self.title_label)

        self.key_facts_scroll = QScrollArea()
        self.key_facts_scroll.setWidgetResizable(True)
        self.key_facts_widget = QWidget()
        self.key_facts_layout = QVBoxLayout(self.key_facts_widget)
        self.key_facts_layout.setContentsMargins(0, 0, 0, 0)
        self.key_facts_layout.setSpacing(6)
        self.key_facts_scroll.setWidget(self.key_facts_widget)
        left_layout.addWidget(self.key_facts_scroll, stretch=1)
        left_layout.addStretch()

        self.splitter.addWidget(self.left_panel)

        # ───── Правая колонка ─────
        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.splitter.addWidget(self.tabs)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

        # ───── Вкладка: Инфо ─────
        self.info_tab = QWidget()
        self.info_layout = QVBoxLayout(self.info_tab)
        self.info_layout.setContentsMargins(0, 0, 0, 0)
        self.info_layout.setSpacing(6)
        self.populate_info_tab()
        self.tabs.addTab(self.info_tab, "Информация")

        # ───── Кнопки ─────
        btns = QHBoxLayout()
        self.edit_btn = styled_button(
            "Редактировать", icon="✏️", shortcut="F2"
        )
        self.delete_btn = styled_button(
            "Удалить", icon="🗑️", role="danger", shortcut="Del"
        )
        self.edit_btn.clicked.connect(self.edit)
        self.delete_btn.clicked.connect(self.delete)
        btns.addStretch()
        btns.addWidget(self.edit_btn)
        btns.addWidget(self.delete_btn)
        self.layout.addLayout(btns)

        self._apply_default_splitter_sizes(size.width())
        self._restore_splitter_state()

    def get_title(self) -> str:
        """Заголовок карточки (по умолчанию строковое представление объекта)."""
        return str(self.instance)

    def populate_info_tab(self):
        """Автоматически выводит все поля модели."""
        self._clear_layout(self.key_facts_layout)
        self._clear_layout(self.info_layout)
        if not hasattr(self.instance, "_meta") or not hasattr(
            self.instance._meta, "sorted_fields"
        ):
            empty_lbl = QLabel("Нет информации для отображения.")
            self.key_facts_layout.addWidget(QLabel("Нет информации."))
            self.key_facts_layout.addStretch()
            self.info_layout.addWidget(empty_lbl)
            self.info_layout.addStretch()
            return
        for field in self.instance._meta.sorted_fields:
            name = field.name
            value = getattr(self.instance, name)
            if hasattr(value, "__str__"):
                value = str(value)

            text = f"<b>{name}:</b> {value if value is not None else '—'}"
            summary_label = QLabel(text)
            summary_label.setTextFormat(Qt.RichText)
            summary_label.setWordWrap(True)
            self.key_facts_layout.addWidget(summary_label)

            label = QLabel(text)
            label.setTextFormat(Qt.RichText)
            label.setWordWrap(True)
            self.info_layout.addWidget(label)

        self.key_facts_layout.addStretch()
        self.info_layout.addStretch()

    def edit(self):
        """Редактировать объект — переопределяется в потомках."""
        pass

    def delete(self):
        """Удалить объект — переопределяется в потомках."""
        pass

    def add_tab(self, widget: QWidget, title: str):
        """Добавить дополнительную вкладку."""
        self.tabs.addTab(widget, title)

    def closeEvent(self, event):
        self._save_splitter_state()
        super().closeEvent(event)

    def _apply_default_splitter_sizes(self, total_width: int | None = None) -> None:
        total = total_width or self.width() or 1
        left = int(total * 0.35)
        right = max(1, total - left)
        self.splitter.setSizes([left, right])

    def _restore_splitter_state(self) -> None:
        key = self.get_settings_key()
        if not key:
            return
        state = ui_settings.get_window_settings(key).get("splitter_state")
        if state:
            try:
                self.splitter.restoreState(base64.b64decode(state))
                return
            except Exception:
                pass
        self._apply_default_splitter_sizes()

    def _save_splitter_state(self) -> None:
        key = self.get_settings_key()
        if not key:
            return
        st = ui_settings.get_window_settings(key)
        st["splitter_state"] = base64.b64encode(self.splitter.saveState()).decode("ascii")
        ui_settings.set_window_settings(key, st)

    def get_settings_key(self) -> str | None:
        return self.SETTINGS_KEY or type(self).__name__

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
