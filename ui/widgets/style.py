from PySide6.QtWidgets import QLabel


def header_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("class", "header")
    return label
