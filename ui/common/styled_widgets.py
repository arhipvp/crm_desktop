from PySide6.QtWidgets import QPushButton
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
    text = f"{icon} {label}".strip()

    if shortcut:
        btn.setShortcut(QKeySequence(shortcut))
        text += f"<br/><span style='color:gray;font-size:8pt'>{shortcut}</span>"

    btn.setText(text)

    if tooltip:
        btn.setToolTip(tooltip)
    if role:
        btn.setProperty("role", role)

    btn.setMinimumHeight(40 if shortcut else 30)

    return btn
