from PySide6.QtWidgets import QPushButton


class RefreshButton(QPushButton):
    def __init__(self, callback, parent=None):
        super().__init__("🔄 Обновить", parent)
        self.clicked.connect(callback)
        self.setFixedHeight(30)
        self.setFixedWidth(120)
