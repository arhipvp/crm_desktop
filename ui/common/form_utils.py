from PySide6.QtWidgets import QLineEdit, QTextEdit, QComboBox


def is_empty(widget) -> bool:
    """Проверка, пуст ли QLineEdit или QTextEdit."""
    if isinstance(widget, QLineEdit):
        return widget.text().strip() == ""
    if isinstance(widget, QTextEdit):
        return widget.toPlainText().strip() == ""
    return True


def get_text_safe(widget) -> str:
    """Получает текст из QLineEdit или QTextEdit без пробелов."""
    if isinstance(widget, QLineEdit):
        return widget.text().strip()
    if isinstance(widget, QTextEdit):
        return widget.toPlainText().strip()
    return ""


def get_selected_id(combo: QComboBox) -> int | None:
    """Возвращает текущий selectedData() из QComboBox."""
    return combo.currentData()


def set_combo_index(combo: QComboBox, value):
    """Устанавливает индекс в QComboBox по значению data()."""
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)

def clear_widget(widget):
    """Очищает QLineEdit, QTextEdit, QComboBox."""
    if isinstance(widget, QLineEdit):
        widget.clear()
    elif isinstance(widget, QTextEdit):
        widget.clear()
    elif isinstance(widget, QComboBox):
        widget.setCurrentIndex(-1)

def set_text_safe(widget, text: str):
    """Устанавливает текст в QLineEdit или QTextEdit."""
    if isinstance(widget, QLineEdit):
        widget.setText(text)
    elif isinstance(widget, QTextEdit):
        widget.setPlainText(text)
