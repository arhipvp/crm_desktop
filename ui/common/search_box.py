from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton


class SearchBox(QWidget):
    def __init__(self, search_callback, parent=None):
        """
        search_callback: функция, вызываемая при вводе текста или очистке поля
        """
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск...")
        self.search_input.textChanged.connect(search_callback)
        layout.addWidget(self.search_input)

        self.clear_btn = QPushButton("❌")
        self.clear_btn.setFixedWidth(30)
        self.clear_btn.clicked.connect(self.clear_search)
        layout.addWidget(self.clear_btn)

    def clear_search(self):
        self.search_input.clear()

    def get_text(self) -> str:
        return self.search_input.text().strip()

    def set_text(self, text: str):
        self.search_input.setText(text)
