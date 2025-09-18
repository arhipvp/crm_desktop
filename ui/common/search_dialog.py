from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
)


class SearchDialog(QDialog):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выберите элемент")

        self.items = [self._normalize_item(item) for item in items]
        self.filtered_items = list(self.items)
        self.selected_index = None

        self.model = QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels(["Вариант", "Комментарий"])

        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Поиск...")
        self.search.textChanged.connect(self.filter_items)
        self.search.returnPressed.connect(self.accept_first)

        self.table_view = QTableView(self)
        self.table_view.setModel(self.model)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setSelectionMode(QTableView.SingleSelection)
        self.table_view.setEditTriggers(QTableView.NoEditTriggers)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.clicked.connect(self._on_row_selected)
        self.table_view.doubleClicked.connect(self.accept_current)

        self.ok_button = QPushButton("OK", self)
        self.ok_button.clicked.connect(self.accept_current)

        self.first_button = QPushButton("Выбрать первый", self)
        self.first_button.clicked.connect(self.accept_first)

        self._update_model()

        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        layout.addWidget(self.table_view)

        button_row = QHBoxLayout()
        button_row.addWidget(self.first_button)
        button_row.addStretch(1)
        button_row.addWidget(self.ok_button)
        layout.addLayout(button_row)

    def filter_items(self, text):
        query = text.strip().lower()
        if not query:
            self.filtered_items = list(self.items)
        else:
            self.filtered_items = [
                item
                for item in self.items
                if query in item["label"].lower()
                or query in item["description"].lower()
            ]
        self._update_model()

    def _update_model(self):
        self.model.setRowCount(0)
        for item in self.filtered_items:
            label_item = QStandardItem(item["label"])
            label_item.setEditable(False)
            description_item = QStandardItem(item["description"])
            description_item.setEditable(False)
            self.model.appendRow([label_item, description_item])

        if self.model.rowCount() > 0:
            first = self.model.index(0, 0)
            self.table_view.setCurrentIndex(first)
            self.table_view.selectRow(0)
        else:
            self.selected_index = None

    def _on_row_selected(self, index):
        if not index.isValid():
            self.selected_index = None
            return
        row = index.row()
        if 0 <= row < len(self.filtered_items):
            self.selected_index = self.filtered_items[row]["value"]

    def accept_current(self, index=None):
        if index is None:
            index = self.table_view.currentIndex()
        if not index.isValid():
            if self.model.rowCount() == 0:
                return
            index = self.model.index(0, 0)
        self._on_row_selected(index)
        if self.selected_index is not None:
            self.accept()

    def accept_first(self):
        if self.model.rowCount() == 0:
            return
        index = self.model.index(0, 0)
        self.table_view.setCurrentIndex(index)
        self._on_row_selected(index)
        if self.selected_index is not None:
            self.accept()

    @staticmethod
    def _normalize_item(item):
        if isinstance(item, dict):
            label = str(item.get("label", ""))
            description = str(item.get("description", ""))
            value = item.get("value", item.get("label"))
        else:
            label = str(item)
            description = ""
            value = item
        return {"label": label, "description": description, "value": value}
