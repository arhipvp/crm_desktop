from PySide6.QtWidgets import QPushButton
from PySide6.QtGui import QKeySequence

def styled_button(
    label: str,
    icon: str = "",
    tooltip: str = "",
    shortcut: str = "",
    role: str = None
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
    btn = QPushButton(f"{icon} {label}" if icon else label)
    if tooltip:
        btn.setToolTip(tooltip)
    if shortcut:
        btn.setShortcut(QKeySequence(shortcut))
    if role:
        btn.setProperty("role", role)
    btn.setMinimumHeight(30)
    return btn
