import logging

logger = logging.getLogger(__name__)

from peewee import Field
from PySide6.QtCore import Qt, Signal, QSortFilterProxyModel
from PySide6.QtGui import QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QMenu,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QMessageBox,
)

from ui.base.table_controller import TableController
from ui.common.filter_controls import FilterControls
from ui.common.paginator import Paginator
from ui.common.styled_widgets import styled_button
from ui.common.column_filter_row import ColumnFilterRow
from ui import settings as ui_settings
from services.folder_utils import open_folder, copy_text_to_clipboard
from services.export_service import export_objects_to_csv
from database.models import Deal


class BaseTableView(QWidget):
    row_double_clicked = Signal(object)  # объект строки по двойному клику
    data_loaded = Signal(int)  # сигнал о загрузке данных (количество)

    # Соответствие индекса столбца полю модели. Значение ``None`` скрывает фильтр.
    COLUMN_FIELD_MAP: dict[int, Field | None] = {}

    def _on_filter_controls_changed(self, *args, **kwargs):
        """Безопасно обрабатывает изменение фильтров во время инициализации."""
        if hasattr(self, "filter_controls"):
            self.on_filter_changed(*args, **kwargs)

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
        can_restore=True,
        restore_callback=None,
        date_filter_field=None,
        filter_func=None,
        custom_actions=None,
        detail_view_class=None,
        controller: TableController | None = None,
        **kwargs,
    ):
        super().__init__(parent)

        self.form_class = form_class
        self.can_edit = can_edit
        self.can_delete = can_delete
        self.can_add = can_add
        self.edit_callback = edit_callback
        self.delete_callback = delete_callback
        self.can_restore = can_restore
        self.restore_callback = restore_callback
        self.custom_actions = custom_actions or []
        self.detail_view_class = detail_view_class

        self.controller = controller or TableController(
            self,
            model_class=model_class,
            get_page_func=get_page_func,
            get_total_func=get_total_func,
            filter_func=filter_func,
        )
        self.model_class = self.controller.model_class

        self.use_inline_details = True
        self.detail_widget = None
        self.settings_id = type(self).__name__

        self.default_sort_column = 0
        self.default_sort_order = Qt.AscendingOrder
        self.current_sort_column = self.default_sort_column
        self.current_sort_order = self.default_sort_order

        self.page = 1
        self.per_page = 30
        self.total_count = 0

        saved_settings = ui_settings.get_table_settings(self.settings_id) or {}
        try:
            self.per_page = int(saved_settings.get("per_page", self.per_page))
        except (TypeError, ValueError):
            pass

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
            search_callback=self._on_filter_controls_changed,
            checkbox_map=checkbox_map,
            on_filter=self._on_filter_controls_changed,
            export_callback=self.export_csv,
            settings_name=self.settings_id,
            date_filter_field=date_filter_field,
            reset_callback=self._on_reset_filters,
        )

        self.left_layout.addWidget(self.filter_controls)
        QShortcut("Ctrl+F", self, activated=self.filter_controls.focus_search)

        # Кнопки
        self.button_row = QHBoxLayout()

        self.add_btn = styled_button("Добавить", icon="➕", role="primary", shortcut="Ctrl+N")
        self.add_btn.clicked.connect(self.add_new)
        self.button_row.addWidget(self.add_btn)
        self.add_btn.setVisible(self.can_add)

        self.edit_btn = styled_button("Редактировать", icon="✏️", shortcut="F2")
        self.edit_btn.setVisible(self.can_edit)
        self.edit_btn.clicked.connect(self._on_edit)
        self.button_row.addWidget(self.edit_btn)

        self.delete_btn = styled_button("Удалить", icon="🗑️", role="danger", shortcut="Del")
        self.delete_btn.clicked.connect(self._on_delete)
        self.button_row.addWidget(self.delete_btn)
        self.delete_btn.setVisible(self.can_delete)

        self.restore_btn = styled_button("Восстановить", icon="♻️", shortcut="Ctrl+R")
        self.restore_btn.clicked.connect(self._on_restore)
        self.button_row.addWidget(self.restore_btn)
        self.restore_btn.setVisible(self.can_restore)

        self.refresh_btn = styled_button("Обновить", icon="🔄", tooltip="Обновить список", shortcut="F5")
        self.refresh_btn.clicked.connect(self.refresh)
        self.button_row.addWidget(self.refresh_btn)

        self.select_all_btn = styled_button("Выделить все", shortcut="Ctrl+A")
        self.select_all_btn.clicked.connect(self._select_all_rows)
        self.button_row.addWidget(self.select_all_btn)

        self.button_row.addStretch()
        self.left_layout.addLayout(self.button_row)

        # Таблица
        self.table = QTableView()
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSortRole(Qt.UserRole)
        self.proxy_model.setDynamicSortFilter(True)
        self.table.setEditTriggers(QTableView.NoEditTriggers)

        self.table.setModel(None)
        self.table.setSortingEnabled(True)
        header = self.table.horizontalHeader()
        header.setSectionsMovable(True)
        header.sortIndicatorChanged.connect(self._on_sort_indicator_changed)
        header.sectionResized.connect(self._on_section_resized)
        header.sectionMoved.connect(self._on_section_moved)
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._on_header_menu)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setAlternatingRowColors(True)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_menu)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        self.left_layout.addWidget(self.table)

        self.column_filters = ColumnFilterRow(linked_view=self.table)
        self.column_filters.filter_changed.connect(self._on_column_filter_changed)
        self.left_layout.insertWidget(self.left_layout.count() - 1, self.column_filters)

        # Пагинация
        self.paginator = Paginator(on_prev=self.prev_page, on_next=self.next_page, per_page=self.per_page)
        self.paginator.per_page_changed.connect(self._on_per_page_changed)
        self.left_layout.addWidget(self.paginator)

    def set_model_class_and_items(self, model_class, items, total_count=None):
        if self.controller:
            self.controller.set_model_class_and_items(model_class, items, total_count)

    def load_data(self):
        if self.controller:
            self.controller.load_data()

    def refresh(self):
        if self.controller:
            self.controller.refresh()

    def on_filter_changed(self, *args, **kwargs):
        if self.controller:
            self.controller.on_filter_changed(*args, **kwargs)

    def next_page(self):
        if self.controller:
            self.controller.next_page()

    def prev_page(self):
        if self.controller:
            self.controller.prev_page()

    def _on_per_page_changed(self, per_page: int):
        if self.controller:
            self.controller._on_per_page_changed(per_page)

    def _on_column_filter_changed(self, column: int, text: str):
        if self.controller:
            self.controller._on_column_filter_changed(column, text)

    def _on_reset_filters(self):
        if self.controller:
            self.controller._on_reset_filters()

    def get_column_filters(self) -> dict[Field, str]:
        if self.controller:
            return self.controller.get_column_filters()
        return {}

    def get_filters(self) -> dict:
        if self.controller:
            return self.controller.get_filters()
        return {}

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
            self.detail_widget.setParent(None)
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

    def _on_restore(self):
        if hasattr(self, "restore_callback") and self.restore_callback:
            self.restore_callback()
        elif self.can_restore:
            self.restore_selected_default()

    def _select_all_rows(self):
        """Выделяет все строки в таблице."""
        self.table.selectAll()

    def edit_selected_default(self):
        index = self.table.currentIndex()
        if not index.isValid():
            return
        obj = self.model.get_item(self._source_row(index))

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
                svc = self._get_service_for_model(self.model_class)
                mark_func = getattr(svc, f"mark_{self.model_class.__name__.lower()}_deleted", None)
                if mark_func:
                    mark_func(obj.id)
                self.refresh()
            except Exception as e:
                logger.exception("❌ Ошибка при удалении объекта")
                show_error(str(e))

    def restore_selected_default(self):
        from ui.common.message_boxes import confirm, show_error

        index = self.table.currentIndex()
        if not index.isValid():
            return
        obj = self.model.get_item(self._source_row(index))

        if confirm(f"Восстановить {self.model_class.__name__} №{getattr(obj, 'id', '')}?"):
            try:
                svc = self._get_service_for_model(self.model_class)
                restore_func = getattr(svc, f"restore_{self.model_class.__name__.lower()}", None)
                if restore_func:
                    restore_func(obj.id)
                self.refresh()
            except Exception as e:
                logger.exception("❌ Ошибка при восстановлении объекта")
                show_error(str(e))

    def _get_service_for_model(self, model_class):
        if model_class.__name__ == "Policy":
            from services.policies import policy_service
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
            from services import task_crud
            return task_crud
        if model_class.__name__ == "Expense":
            from services import expense_service
            return expense_service
        if model_class.__name__ == "DealCalculation":
            from services import calculation_service
            return calculation_service
        if model_class.__name__ == "Client":
            from services.clients import client_service
            return client_service

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

    def get_selected_objects(self) -> list:
        if not self.model:
            return []
        sel = self.table.selectionModel().selectedRows()
        return [self.model.get_item(self._source_row(i)) for i in sel if i.isValid()]

    def get_selected_deal(self) -> Deal | None:
        """Возвращает связанную сделку для выбранной строки."""
        return None

    def open_selected_folder(self):
        """Открыть связанную папку для выбранной строки."""
        obj = self.get_selected_object()
        if not obj:
            return
        path = getattr(obj, "drive_folder_path", None) or getattr(obj, "drive_folder_link", None)
        if path:
            open_folder(path, parent=self)

    def open_selected_deal(self):
        """Открыть связанную сделку для выбранной строки."""
        deal = self.get_selected_deal()
        if not deal:
            return
        from ui.views.deal_detail import DealDetailView
        DealDetailView(deal, parent=self).exec()

    def export_csv(self, path: str | None = None, *, all_rows: bool = False, **_):
        """Экспорт объектов в CSV.

        - Логируем шаги (info/debug/warning).
        - Поддерживаем странный вызов с bool вместо пути (приводим к None).
        - Экспортируем только видимые колонки (по columnCount()).
        - Если ``all_rows`` истинен, экспортируем все строки модели.
        """
        if isinstance(path, bool):
            path = None

        objs = getattr(self.model, "objects", None) if all_rows else self.get_selected_objects()
        if all_rows and objs is None:
            # запасной путь на случай, если модель не хранит objects
            try:
                objs = [self.model.get_item(r) for r in range(self.model.rowCount())]
            except Exception:
                objs = []
        logger.info("Запрошен экспорт %d строк", len(objs))

        if not objs:
            logger.warning("Нет выбранных строк для экспорта")
            QMessageBox.warning(self, "Экспорт", "Нет выбранных строк")
            return

        if path is None:
            options = QFileDialog.Options()
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Сохранить как CSV",
                "",
                "CSV Files (*.csv);;All Files (*)",
                options=options,
            )
        if not path:
            logger.warning("Экспорт отменён пользователем")
            return

        # Выбираем только видимые поля модели и/или из COLUMN_FIELD_MAP.
        try:
            column_count = self.model.columnCount()
        except Exception:
            column_count = len(getattr(self.model, "fields", []))

        model_fields = getattr(self.model, "fields", [])
        column_map = getattr(self, "COLUMN_FIELD_MAP", {})
        visible_indices = [i for i in range(column_count) if not self.table.isColumnHidden(i)]

        fields = []
        for i in visible_indices:
            if len(model_fields) > i:
                fields.append(model_fields[i])
            else:
                fields.append(column_map.get(i))
        fields = [f for f in fields if f is not None]
        if len(fields) < len(visible_indices):
            logger.warning("Найдено полей: %d < %d колонок", len(fields), len(visible_indices))

        # Заголовки берём из модели, если есть.
        try:
            headers = [self.model.headerData(i, Qt.Horizontal, Qt.DisplayRole) for i in visible_indices]
        except Exception:
            headers = None

        logger.debug("Заголовки CSV: %s", [getattr(f, "name", str(f)) for f in fields])
        logger.debug("Количество объектов к экспорту: %d", len(objs))
        logger.debug("Сохраняем CSV в %s", path)

        try:
            export_objects_to_csv(path, objs, fields, headers=headers)
        except Exception as e:
            logger.exception("Ошибка экспорта CSV")
            QMessageBox.critical(self, "Экспорт", str(e))
        else:
            logger.info("Экспортировано %d строк в %s", len(objs), path)
            QMessageBox.information(self, "Экспорт", f"Экспортировано: {len(objs)}")

    def _on_row_double_clicked(self, index):
        if not index.isValid():
            return
        obj = self.model.get_item(self._source_row(index))
        self.row_double_clicked.emit(obj)

    def _on_table_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        self.table.selectRow(index.row())
        menu = QMenu(self)
        act_open = menu.addAction("Открыть/редактировать")
        act_delete = menu.addAction("Удалить")
        act_folder = menu.addAction("Открыть папку")
        has_path = bool(
            getattr(self.get_selected_object(), "drive_folder_path", None)
            or getattr(self.get_selected_object(), "drive_folder_link", None)
        )
        text = str(index.data() or "")
        act_copy = menu.addAction("Копировать значение")
        act_deal = menu.addAction("Открыть сделку")
        act_open.triggered.connect(self._on_edit)
        act_delete.triggered.connect(self._on_delete)
        act_folder.triggered.connect(self.open_selected_folder)
        act_copy.triggered.connect(lambda: copy_text_to_clipboard(text, parent=self))
        act_deal.triggered.connect(self.open_selected_deal)
        act_deal.setEnabled(bool(self.get_selected_deal()))
        act_folder.setEnabled(has_path)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_header_menu(self, pos):
        header = self.table.horizontalHeader()
        menu = QMenu(self)
        for i in range(header.count()):
            text = header.model().headerData(i, Qt.Horizontal)
            action = menu.addAction(str(text))
            action.setCheckable(True)
            action.setChecked(not header.isSectionHidden(i))
            action.toggled.connect(lambda checked, i=i: self._toggle_column(i, checked))
        menu.exec(header.mapToGlobal(pos))

    def _toggle_column(self, index: int, visible: bool):
        self.table.setColumnHidden(index, not visible)
        self.column_filters.set_editor_visible(index, visible)
        self.save_table_settings()

    def _on_sort_indicator_changed(self, column: int, order: Qt.SortOrder):
        """Сохраняет текущую сортировку таблицы."""
        self.current_sort_column = column
        self.current_sort_order = order
        self.save_table_settings()

    def _on_section_resized(self, *_):
        self.save_table_settings()

    def _on_section_moved(self, *_):
        self.save_table_settings()

    def save_table_settings(self):
        """Сохраняет настройки сортировки и ширины колонок."""
        header = self.table.horizontalHeader()
        widths = {i: header.sectionSize(i) for i in range(header.count())}
        hidden = [i for i in range(header.count()) if self.table.isColumnHidden(i)]
        order = [header.visualIndex(i) for i in range(header.count())]
        texts = self.column_filters.get_all_texts()
        settings = {
            "sort_column": self.current_sort_column,
            "sort_order": self.current_sort_order.value,
            "column_widths": widths,
            "hidden_columns": hidden,
            "column_order": order,
            "column_filter_texts": texts,
            "per_page": self.per_page,
        }
        ui_settings.set_table_settings(self.settings_id, settings)

    def load_table_settings(self):
        """Применяет сохранённые настройки, если они есть."""
        header = self.table.horizontalHeader()
        saved = ui_settings.get_table_settings(self.settings_id)
        if not saved:
            return
        column = saved.get("sort_column")
        order = saved.get("sort_order")
        if column is not None and order is not None:
            try:
                header.setSortIndicator(int(column), Qt.SortOrder(order))
                self.current_sort_column = int(column)
                self.current_sort_order = Qt.SortOrder(order)
            except Exception:
                pass
        order_list = saved.get("column_order")
        if order_list and len(order_list) == header.count():
            header.blockSignals(True)
            try:
                for logical, visual in sorted(enumerate(order_list), key=lambda x: x[1]):
                    current_visual = header.visualIndex(logical)
                    if current_visual != visual:
                        header.moveSection(current_visual, visual)
            finally:
                header.blockSignals(False)
        for idx, width in saved.get("column_widths", {}).items():
            idx = int(idx)
            if idx < header.count():
                header.resizeSection(idx, width)
        model = self.table.model()
        model_columns = model.columnCount() if model else 0
        for idx in saved.get("hidden_columns", []):
            idx = int(idx)
            if idx < model_columns:
                self.table.setColumnHidden(idx, True)
                self.column_filters.set_editor_visible(idx, False)
        texts = saved.get("column_filter_texts", [])
        if texts:
            self.column_filters.set_all_texts(texts)
        per_page = saved.get("per_page")
        need_reload = False
        if per_page is not None:
            try:
                per_page = int(per_page)
                if per_page != self.per_page:
                    self.per_page = per_page
                    need_reload = True
            except (TypeError, ValueError):
                pass
        self.paginator.update(self.total_count, self.page, self.per_page)
        if need_reload:
            self.load_data()

    def closeEvent(self, event):
        self.save_table_settings()
        super().closeEvent(event)
