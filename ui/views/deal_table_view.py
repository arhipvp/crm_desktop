from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from ui.base.base_table_model import BaseTableModel

from database.models import Deal
from services.deal_service import build_deal_query, get_deals_page, mark_deal_deleted
from ui.base.base_table_view import BaseTableView
from ui.common.message_boxes import confirm, show_error
from ui.forms.deal_form import DealForm
from ui.views.deal_detail_view import DealDetailView


class DealTableModel(BaseTableModel):
    def __init__(self, objects, model_class, parent=None):
        super().__init__(objects, model_class, parent)

        # скрываем ссылку на папку и двигаем колонки закрытия в конец
        self.fields = [f for f in self.fields if f.name != "drive_folder_link"]

        def move_to_end(field_name):
            for i, f in enumerate(self.fields):
                if f.name == field_name:
                    self.fields.append(self.fields.pop(i))
                    break

        move_to_end("is_closed")
        move_to_end("closed_reason")

        self.headers = [f.name for f in self.fields]
        self.virtual_fields = ["executor"]
        self.headers.append("Исполнитель")

    def columnCount(self, parent=None):
        return len(self.fields) + len(self.virtual_fields)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        obj = self.objects[index.row()]
        if role == Qt.ForegroundRole and getattr(obj, "_executor", None):
            return QColor("red")
        col = index.column()
        if col >= len(self.fields):
            if role == Qt.DisplayRole:
                ex = getattr(obj, "_executor", None)
                return ex.full_name if ex else "—"
            return None
        return super().data(index, role)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        if section < len(self.fields):
            return super().headerData(section, orientation, role)
        return self.headers[-1]


class DealTableView(BaseTableView):
    def __init__(self, parent=None):
        checkboxes = {
            "Показывать удалённые": self.on_filter_changed,
            "Показать закрытые": self.on_filter_changed,
        }
        super().__init__(
            parent=parent,
            model_class=Deal,
            form_class=DealForm,
            detail_view_class=DealDetailView,
            checkbox_map=checkboxes,
        )

        self.sort_field = "reminder_date"
        self.sort_order = "asc"  # 'asc' or 'desc'
        self.default_sort_field = "reminder_date"

        self.table.horizontalHeader().sortIndicatorChanged.connect(
            self.on_sort_changed
        )
        self.row_double_clicked.connect(self.open_detail)

        self.load_data()

    def get_filters(self) -> dict:
        """
        Собираем все фильтры:
         - текстовый поиск
         - флаг 'Показывать удалённые' из BaseTableView
        """
        filters = super().get_filters()
        filters.update(
            {
                "show_closed": self.filter_controls.is_checked("Показать закрытые"),
            }
        )
        return filters

    def load_data(self):
        filters = self.get_filters()

        # Получаем имя поля сортировки (self.sort_field)
        items = get_deals_page(
            self.page,
            self.per_page,
            order_by=self.sort_field,
            order_dir=self.sort_order,
            **filters,
        )
        total = build_deal_query(**filters).count()
        self.set_model_class_and_items(Deal, list(items), total_count=total)

    def set_model_class_and_items(self, model_class, items, total_count=None):
        self.model = DealTableModel(items, model_class)
        self.proxy_model.setSourceModel(self.model)
        self.table.setModel(self.proxy_model)

        try:
            self.table.sortByColumn(self.current_sort_column, self.current_sort_order)
            self.table.resizeColumnsToContents()
        except NotImplementedError:
            pass

        if total_count is not None:
            self.total_count = total_count
            self.paginator.update(self.total_count, self.page, self.per_page)
            self.data_loaded.emit(self.total_count)

        headers = [
            self.model.headerData(i, Qt.Horizontal)
            for i in range(self.model.columnCount())
        ]
        self.column_filters.set_headers(headers)

        # какой столбец сейчас является полем сортировки?
        col = self.get_column_index(self.sort_field)
        order = Qt.DescendingOrder if self.sort_order == "desc" else Qt.AscendingOrder

        # показываем пользователю правильный индикатор сортировки
        self.table.horizontalHeader().setSortIndicator(col, order)
        # и не даём базовому классу перезаписывать порядок

    def get_selected(self):
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        return self.model.get_item(self._source_row(index))

    def add_new(self):
        form = DealForm()
        if form.exec():
            self.refresh()
            if form.instance:
                dlg = DealDetailView(form.instance, parent=self)
                dlg.exec()

    def edit_selected(self, _=None):
        deal = self.get_selected()
        if deal:
            dlg = DealDetailView(deal, parent=self)
            dlg.exec()
            self.refresh()  # обновить таблицу после возможных изменений

    def delete_selected(self):
        deal = self.get_selected()
        if deal and confirm(f"Удалить сделку {deal.description}?"):
            try:
                mark_deal_deleted(deal.id)
                self.refresh()
            except Exception as e:
                show_error(str(e))

    def open_detail(self, _=None):
        deal = self.get_selected()
        if deal:
            dlg = DealDetailView(deal)
            dlg.exec()

    def on_sort_changed(self, column: int, order: Qt.SortOrder):
        """Refresh data after the user changed sort order."""
        if not self.model or column >= len(self.model.fields):
            return

        self.sort_field = self.model.fields[column].name
        self.sort_order = "desc" if order == Qt.DescendingOrder else "asc"
        self.refresh()
