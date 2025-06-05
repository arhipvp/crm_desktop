from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout
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
    btn.setMinimumHeight(30)
    if role:
        btn.setProperty("role", role)

    layout = QVBoxLayout(btn)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    text = f"{icon} {label}" if icon else label
    main_label = QLabel(text)
    main_label.setAlignment(Qt.AlignCenter)
    layout.addWidget(main_label)

    if shortcut:
        btn.setShortcut(QKeySequence(shortcut))
        hotkey_label = QLabel(shortcut)
        hotkey_label.setAlignment(Qt.AlignCenter)
        hotkey_label.setStyleSheet("color: gray; font-size: 8pt;")
        layout.addWidget(hotkey_label)

    if tooltip:
        btn.setToolTip(tooltip)

    return btn
