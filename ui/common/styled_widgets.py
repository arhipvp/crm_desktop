from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QSizePolicy
from PySide6.QtGui import QKeySequence
from PySide6.QtCore import Qt


def styled_button(
    label: str, icon: str = "", tooltip: str = "", shortcut: str = "", role: str = None
) -> QPushButton:
    """
    Создаёт стилизованную кнопку с иконкой, подсказкой и шорткатом.

    Parameters
    ----------
    label : str
        Текст кнопки
    icon : str
        Эмоджи или иконка
    tooltip : str
        Всплывающая подсказка
    shortcut : str
        Горячая клавиша, например: "Ctrl+S"
    role : str
        Визуальная роль ("primary", "danger")
    """
    btn = QPushButton()
    layout = QVBoxLayout(btn)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    text_label = QLabel(f"{icon} {label}".strip())
    text_label.setAlignment(Qt.AlignCenter)
    text_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
    layout.addWidget(text_label)

    width = text_label.fontMetrics().horizontalAdvance(text_label.text())

    if shortcut:
        btn.setShortcut(QKeySequence(shortcut))
        shortcut_label = QLabel(shortcut)
        shortcut_label.setAlignment(Qt.AlignCenter)
        shortcut_label.setStyleSheet("color: gray; font-size: 8pt")
        shortcut_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        layout.addWidget(shortcut_label)
        width = max(width, shortcut_label.fontMetrics().horizontalAdvance(shortcut))
    
    if tooltip:
        btn.setToolTip(tooltip)
    if role:
        btn.setProperty("role", role)

    btn.setMinimumHeight(40 if shortcut else 30)
    btn.setMinimumWidth(width + 20)
    btn.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)

    return btn
