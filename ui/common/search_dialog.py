from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListView, QPushButton
from PySide6.QtCore import QStringListModel


class SearchDialog(QDialog):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выберите элемент")

        self.model = QStringListModel(items)
        self.filtered_items = items
        self.selected_index = None

        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Поиск...")
        self.search.textChanged.connect(self.filter_items)

        self.list_view = QListView(self)
        self.list_view.setModel(self.model)
        self.list_view.clicked.connect(self.select_item)

        self.ok_button = QPushButton("OK", self)
        self.ok_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        layout.addWidget(self.list_view)
        layout.addWidget(self.ok_button)

    def filter_items(self, text):
        filtered = [
            item for item in self.filtered_items if text.lower() in item.lower()
        ]
        self.model.setStringList(filtered)

    def select_item(self, index):
        self.selected_index = index.data()
