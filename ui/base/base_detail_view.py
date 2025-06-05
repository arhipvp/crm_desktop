from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.common.styled_widgets import styled_button


class BaseDetailView(QDialog):
    def __init__(self, instance, title=None, parent=None):
        super().__init__(parent)
        self.instance = instance
        self.setWindowTitle(title or f"{type(instance).__name__} — Подробнее")
        self.setMinimumSize(600, 500)

        self.layout = QVBoxLayout(self)

        # ───── Заголовок ─────
        title_str = self.get_title()
        self.title_label = QLabel(title_str)
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.layout.addWidget(self.title_label)

        # ───── Табы ─────
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # ───── Вкладка: Инфо ─────
        self.info_tab = QWidget()
        self.info_layout = QVBoxLayout(self.info_tab)
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

    def get_title(self) -> str:
        """Заголовок карточки (по умолчанию строковое представление объекта)."""
        return str(self.instance)

    def populate_info_tab(self):
        """Автоматически выводит все поля модели."""
        if not hasattr(self.instance, "_meta") or not hasattr(
            self.instance._meta, "sorted_fields"
        ):
            self.info_layout.addWidget(QLabel("Нет информации для отображения."))
            return
        for field in self.instance._meta.sorted_fields:
            name = field.name
            value = getattr(self.instance, name)
            if hasattr(value, "__str__"):
                value = str(value)

            label = QLabel(f"<b>{name}:</b> {value if value is not None else '—'}")
            label.setTextFormat(Qt.RichText)
            self.info_layout.addWidget(label)

    def edit(self):
        """Редактировать объект — переопределяется в потомках."""
        pass

    def delete(self):
        """Удалить объект — переопределяется в потомках."""
        pass

    def add_tab(self, widget: QWidget, title: str):
        """Добавить дополнительную вкладку."""
        self.tabs.addTab(widget, title)
