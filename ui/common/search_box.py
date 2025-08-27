from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit


class SearchBox(QWidget):
    def __init__(self, search_callback, parent=None):
        """
        search_callback: функция, вызываемая при вводе текста
        """
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(search_callback)
        layout.addWidget(self.search_input)

    def get_text(self) -> str:
        return self.search_input.text().strip()

    def set_text(self, text: str):
        self.search_input.setText(text)
