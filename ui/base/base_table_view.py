import logging

logger = logging.getLogger(__name__)

from PySide6.QtCore import (QDate, QRegularExpression, QSortFilterProxyModel,
                            Qt, Signal)
from PySide6.QtWidgets import (QHBoxLayout, QHeaderView, QSplitter, QTableView,
                               QVBoxLayout, QWidget)

from ui.base.base_edit_form import BaseEditForm
from ui.base.base_table_model import BaseTableModel
from ui.common.filter_controls import FilterControls
from ui.common.paginator import Paginator
from ui.common.styled_widgets import styled_button


class DateAwareSortFilterProxyModel(QSortFilterProxyModel):
    def lessThan(self, left, right):
        left_data = self.sourceModel().data(left, Qt.UserRole)
        right_data = self.sourceModel().data(right, Qt.UserRole)
        if isinstance(left_data, QDate) and isinstance(right_data, QDate):
            return left_data < right_data
        return super().lessThan(left, right)

class BaseTableView(QWidget):
    row_double_clicked = Signal(object)  # объект строки по двойному клику

    def __init__(
        self,
        parent=None,
        *,
        model_class=None,
        form_class=None,
        get_page_func=None,
        get_total_func=None,
        can_edit=True,
        can_delete=True,
        can_add=True,
        edit_callback=None,
        delete_callback=None,
        filter_func=None,
        custom_actions=None,
        detail_view_class=None,
        **kwargs
    ):
        super().__init__(parent)
        
        self.model_class = model_class
        self.form_class = form_class
        self.get_page_func = get_page_func
        self.get_total_func = get_total_func
        self.can_edit = can_edit
        self.can_delete = can_delete
        self.can_add = can_add
        self.edit_callback = edit_callback
        self.delete_callback = delete_callback
        self.filter_func = filter_func
        self.custom_actions = custom_actions or []
        self.detail_view_class = detail_view_class

        
        
        


        self.use_inline_details = True   # включить встроенные детали
        self.detail_widget = None

        self.default_sort_column = 0  # по умолчанию — первый столбец
        self.default_sort_order = Qt.AscendingOrder

        self.page = 1
        self.per_page = 30
        self.total_count = 0

        
        
        
        
        

        # --- мастер-детал макет ---
        self.outer_layout = QVBoxLayout(self)
        self.splitter = QSplitter()
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        self.splitter.addWidget(self.left_panel)
        self.outer_layout.addWidget(self.splitter)
        self.setLayout(self.outer_layout)

        # Фильтры
        checkbox_map = kwargs.get("checkbox_map") or {}
        checkbox_map.setdefault("Показывать удалённые", lambda state: self.on_filter_changed())

        self.filter_controls = FilterControls(
            search_callback=self.on_filter_changed,
            checkbox_map=checkbox_map,  
            on_filter=self.on_filter_changed
        )

        self.left_layout.addWidget(self.filter_controls)

        # Кнопки
        self.button_row = QHBoxLayout()

        self.add_btn = styled_button("Добавить", icon="➕", role="primary")
        self.add_btn.clicked.connect(self.add_new)
        self.button_row.addWidget(self.add_btn)
        self.add_btn.setVisible(self.can_add)

        self.edit_btn = styled_button("Редактировать", icon="✏️")
        self.edit_btn.setVisible(self.can_edit)

        self.edit_btn.clicked.connect(self._on_edit)
        self.button_row.addWidget(self.edit_btn)

        self.delete_btn = styled_button("Удалить", icon="🗑️", role="danger")
        self.delete_btn.clicked.connect(self._on_delete)
        self.button_row.addWidget(self.delete_btn)
        self.delete_btn.setVisible(self.can_delete)

        self.refresh_btn = styled_button("Обновить", icon="🔄", tooltip="Обновить список", shortcut="F5")
        self.refresh_btn.clicked.connect(self.refresh)
        self.button_row.addWidget(self.refresh_btn)


        self.button_row.addStretch()
        self.left_layout.addLayout(self.button_row)

        # Таблица
        self.table = QTableView()
        self.table.setEditTriggers(QTableView.NoEditTriggers)

        self.table.setModel(None)  # Пока модель не установлена
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.left_layout.addWidget(self.table)
        self.proxy_model = DateAwareSortFilterProxyModel(self)
        self.table.setModel(self.proxy_model)

        # Пагинация
        self.paginator = Paginator(on_prev=self.prev_page, on_next=self.next_page)
        self.left_layout.addWidget(self.paginator)

    def set_model_class_and_items(self, model_class, items, total_count=None):
        self.model = BaseTableModel(items, model_class)
        self.proxy_model.setSourceModel(self.model)
        self.table.setModel(self.proxy_model)

        # Безопасная попытка resize
        try:
            self.table.sortByColumn(self.default_sort_column, self.default_sort_order)
            self.table.resizeColumnsToContents()
        except NotImplementedError:
            pass


        
        if total_count is not None:
            self.total_count = total_count
            self.paginator.update(self.total_count, self.page)



    def load_data(self):
        if not self.model_class or not self.get_page_func:
            return

        # 1. Собираем фильтры
        filters = {}
        filters["show_deleted"] = self.filter_controls.is_checked("Показывать удалённые")
        filters["search_text"] = self.filter_controls.get_search_text()


        date_range = self.filter_controls.get_date_filter()
        if date_range:
            filters.update(date_range)

        # 2. Загружаем данные
        items = self.get_page_func(self.page, self.per_page, **filters)
        total = (
            self.get_total_func(**filters) if self.get_total_func
            else len(items)
        )

        # 3. Обновляем таблицу и пагинатор
        self.set_model_class_and_items(self.model_class, list(items), total_count=total)





    def refresh(self):
        self.load_data()

    def on_filter_changed(self, *args, **kwargs):
        self.page = 1
        self.load_data()

    def next_page(self):
        self.page += 1
        self.load_data()

    def prev_page(self):
        if self.page > 1:
            self.page -= 1
            self.load_data()

    def add_new(self):
        if not self.form_class:
            return
        form = self.form_class()
        if form.exec():
            self.refresh()

    def edit_selected(self, _=None):
        self._on_edit()


    def delete_selected(self):
        # Заглушка: потомок может переопределить
        pass


    def set_detail_widget(self, widget):
        """Показывает виджет деталей справа от таблицы."""
        if self.detail_widget:
            self.detail_widget.setParent(None)  # удаляем старый
        self.detail_widget = widget
        self.splitter.addWidget(widget)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)

    def get_column_index(self, field_name: str) -> int:
        if not self.model:
            return 0
        for i, f in enumerate(self.model.fields):
            if f.name == field_name:
                return i
        return 0
    def _on_edit(self):
        if self.edit_callback:
            self.edit_callback()
        elif self.can_edit:
            self.edit_selected_default()

    def _on_delete(self):
        if self.delete_callback:
            self.delete_callback()
        elif self.can_delete:
            self.delete_selected_default()

    def edit_selected_default(self):
        index = self.table.currentIndex()
        if not index.isValid():
            return
        obj = self.model.get_item(self._source_row(index))



        # Вот тут изменяем:
        if self.detail_view_class:
            dlg = self.detail_view_class(obj, parent=self)
            dlg.exec()
            self.refresh()
        elif self.form_class:
            form = self.form_class(obj, parent=self)
            if form.exec():
                self.refresh()



    def delete_selected_default(self):
        from ui.common.message_boxes import confirm, show_error
        index = self.table.currentIndex()
        if not index.isValid():
            return
        obj = self.model.get_item(self._source_row(index))

        if confirm(f"Удалить {self.model_class.__name__} №{getattr(obj, 'id', '')}?"):
            try:
                # Попробуй найти функцию mark_<entity>_deleted по имени модели
                svc = self._get_service_for_model(self.model_class)
                mark_func = getattr(svc, f"mark_{self.model_class.__name__.lower()}_deleted", None)
                if mark_func:
                    mark_func(obj.id)
                self.refresh()
            except Exception as e:
                logger.exception("❌ Ошибка при удалении объекта")
                show_error(str(e))

    def _get_service_for_model(self, model_class):
        # Импортируй нужный сервис по классу модели
        if model_class.__name__ == "Policy":
            from services import policy_service
            return policy_service
        if model_class.__name__ == "Payment":
            from services import payment_service
            return payment_service
        if model_class.__name__ == "Income":
            from services import income_service
            return income_service
        if model_class.__name__ == "Deal":
            from services import deal_service
            return deal_service
        if model_class.__name__ == "Task":
            from services import task_service
            return task_service 
        if model_class.__name__ == "Expense":
            from services import expense_service
            return expense_service
        if model_class.__name__ == "Client":
            from services import client_service
            return client_service


        # Добавь другие сущности по необходимости
        raise ValueError("Нет сервиса для модели", model_class)


    def open_detail_view(self):
        index = self.table.currentIndex()
        if not index.isValid() or not self.detail_view_class:
            return
        obj = self.model.get_item(self._source_row(index))


        dlg = self.detail_view_class(obj, parent=self)
        dlg.exec()
        self.refresh()




    def _source_row(self, view_index):
        """Возвращает номер строки в исходной модели для индекса из таблицы."""
        return self.proxy_model.mapToSource(view_index).row()

    # BaseTableView
    def get_selected_object(self):
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        return self.model.get_item(self._source_row(index))

    