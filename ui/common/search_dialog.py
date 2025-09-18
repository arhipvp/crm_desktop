import base64
import html

from ui import settings as ui_settings

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableView,
    QTextBrowser,
    QVBoxLayout,
)


class SearchDialog(QDialog):
    def __init__(self, items, parent=None, make_deal_callback=None):
        super().__init__(parent)
        self.setWindowTitle("Выберите элемент")

        self.items = [self._normalize_item(item) for item in items]
        self.filtered_items = list(self.items)
        self.selected_index = None
        self._default_details_html = "<p><i>Выберите элемент, чтобы увидеть детали.</i></p>"
        self._make_deal_callback = make_deal_callback

        self.model = QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels(["Оценка", "Сделка", "Комментарий"])
        self.model.setSortRole(Qt.UserRole)

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
        self.table_view.setSortingEnabled(True)
        self.table_view.clicked.connect(self._on_row_selected)
        self.table_view.doubleClicked.connect(self.accept_current)
        self.table_view.selectionModel().currentRowChanged.connect(
            self._on_current_row_changed
        )

        self.detail_view = QTextBrowser(self)
        self.detail_view.setOpenExternalLinks(True)
        self.detail_view.setHtml(self._default_details_html)

        self.ok_button = QPushButton("OK", self)
        self.ok_button.clicked.connect(self.accept_current)

        self.first_button = QPushButton("Выбрать первый", self)
        self.first_button.clicked.connect(self.accept_first)

        self.make_deal_button = None
        if self._make_deal_callback is not None:
            self.make_deal_button = QPushButton("Сделать новую сделку", self)
            self.make_deal_button.clicked.connect(self._on_make_deal_clicked)

        self._update_model()

        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self.table_view)
        splitter.addWidget(self.detail_view)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        button_row = QHBoxLayout()
        button_row.addWidget(self.first_button)
        if self.make_deal_button is not None:
            button_row.addWidget(self.make_deal_button)
        button_row.addStretch(1)
        button_row.addWidget(self.ok_button)
        layout.addLayout(button_row)

        st = ui_settings.get_window_settings("SearchDialog")
        geom = st.get("geometry")
        if geom:
            try:
                self.restoreGeometry(base64.b64decode(geom))
            except Exception:
                pass

    def _on_make_deal_clicked(self):
        if self._make_deal_callback is None:
            return
        self._make_deal_callback()
        self.reject()

    def filter_items(self, text):
        query = text.strip().lower()
        if not query:
            self.filtered_items = list(self.items)
        else:
            self.filtered_items = [
                item
                for item in self.items
                if query in (item.get("title", "").lower())
                or query in (item.get("subtitle", "").lower())
                or query in (item.get("comment", "").lower())
            ]
        self._update_model()

    def _update_model(self):
        self.model.setRowCount(0)
        for item in self.filtered_items:
            score_item = QStandardItem()
            score_item.setEditable(False)
            score_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)

            score = item.get("score")
            if score is not None:
                score_item.setText(f"{score:.2f}")
                score_item.setData(float(score), Qt.UserRole)
            else:
                score_item.setText("")
                score_item.setData(float("-inf"), Qt.UserRole)

            score_item.setData(item, Qt.UserRole + 1)

            title = item.get("title", "")
            subtitle = item.get("subtitle", "")
            if title and subtitle:
                deal_text = f"{title} — {subtitle}"
            else:
                deal_text = title or subtitle
            deal_item = QStandardItem(deal_text)
            deal_item.setEditable(False)

            comment = item.get("comment", "")
            comment_item = QStandardItem(comment)
            comment_item.setEditable(False)

            self.model.appendRow([score_item, deal_item, comment_item])

        if self.model.rowCount() > 0:
            first = self.model.index(0, 0)
            self.table_view.setCurrentIndex(first)
            self.table_view.selectRow(0)
            self._apply_selection(first)
        else:
            self.selected_index = None
            self._set_details_for_item(None)

    def _on_row_selected(self, index):
        self._apply_selection(index)

    def _on_current_row_changed(self, current, previous):
        del previous
        self._apply_selection(current)

    def _apply_selection(self, index):
        if not index.isValid():
            self.selected_index = None
            self._set_details_for_item(None)
            return
        model = index.model()
        if model is None:
            self.selected_index = None
            self._set_details_for_item(None)
            return

        row = index.row()
        source_item = model.item(row, 0)
        if source_item is None:
            self.selected_index = None
            self._set_details_for_item(None)
            return

        item = source_item.data(Qt.UserRole + 1)
        if not isinstance(item, dict):
            self.selected_index = None
            self._set_details_for_item(None)
            return

        self.selected_index = item.get("value")
        self._set_details_for_item(item)

    def _set_details_for_item(self, item):
        if not item:
            self.detail_view.setHtml(self._default_details_html)
            return

        details = item.get("details") or []
        value = item.get("value")
        if details:
            items_html = "".join(
                f"<li>{html.escape(str(reason))}</li>" for reason in details
            )
            content = f"<ul>{items_html}</ul>"
        elif isinstance(value, dict) and value.get("type") == "manual":
            content = "<p><i>Причин нет — ручной выбор</i></p>"
        else:
            content = "<p><i>Причины отсутствуют</i></p>"
        self.detail_view.setHtml(content)

    def accept_current(self, index=None):
        if index is None:
            index = self.table_view.currentIndex()
        if not index.isValid():
            if self.model.rowCount() == 0:
                return
            index = self.model.index(0, 0)

        if index.column() != 0:
            index = index.model().index(index.row(), 0)

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

    def closeEvent(self, event):
        st = {
            "geometry": base64.b64encode(self.saveGeometry()).decode("ascii"),
        }
        ui_settings.set_window_settings("SearchDialog", st)
        super().closeEvent(event)

    @staticmethod
    def _normalize_item(item):
        if isinstance(item, dict):
            score = item.get("score")
            if score is not None:
                try:
                    score = float(score)
                except (TypeError, ValueError):
                    score = None
            title = str(
                item.get(
                    "title",
                    item.get("label", ""),
                )
            )
            subtitle = str(item.get("subtitle", ""))
            comment = str(
                item.get(
                    "comment",
                    item.get("description", ""),
                )
            )
            value = item.get("value", item.get("label"))
            details = [str(detail) for detail in item.get("details", [])]
        else:
            score = None
            title = str(item)
            subtitle = ""
            comment = ""
            value = item
            details = []
        return {
            "score": score,
            "title": title,
            "subtitle": subtitle,
            "comment": comment,
            "label": title,
            "description": comment,
            "value": value,
            "details": details,
        }
