from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QTableView, QVBoxLayout

from database.models import Deal
from services.deal_service import (build_deal_query, get_deals_page,
                                   mark_deal_deleted)
from ui.base.base_table_view import BaseTableView
from ui.common.message_boxes import confirm, show_error
from ui.forms.deal_form import DealForm
from ui.views.deal_detail_view import DealDetailView




class DealTableView(BaseTableView):
    def __init__(self, parent=None):
        checkboxes = {
            "Показывать удалённые": self.refresh,
            "Показать закрытые": self.refresh,
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

        self.table.horizontalHeader().sectionClicked.connect(self.on_sort_requested)
        self.row_double_clicked.connect(self.open_detail)

        self.load_data()


    def get_filters(self) -> dict:
        """
        Собираем все фильтры:
         - текстовый поиск
         - флаг 'Показывать удалённые' из BaseTableView
        """
        return {
            "search_text": self.filter_controls.get_search_text(),
            "show_deleted": self.filter_controls.is_checked("Показывать удалённые"),
            "show_closed": self.filter_controls.is_checked("Показать закрытые"),

        }

    def load_data(self):
        filters = self.get_filters()

        # Получаем имя поля сортировки (self.sort_field)
        items = get_deals_page(
            self.page,
            self.per_page,
            order_by=self.sort_field,
            order_dir=self.sort_order,
            **filters
        )
        total = build_deal_query(**filters).count()
        self.set_model_class_and_items(Deal, list(items), total_count=total)



    def set_model_class_and_items(self, model_class, items, total_count=None):
        super().set_model_class_and_items(model_class, items, total_count)

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

    def on_sort_requested(self, column):
        # Получаем имя поля по индексу
        field = self.model_class._meta.sorted_fields[column]
        field_name = self.model.fields[column].name

        if self.sort_field == field_name:
            # Меняем порядок сортировки, если клик по тому же столбцу
            self.sort_order = "desc" if self.sort_order == "asc" else "asc"
        else:
            # Клик по новому столбцу
            self.sort_field = field_name
            self.sort_order = "asc"
        self.refresh()
