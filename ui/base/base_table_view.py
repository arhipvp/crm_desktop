from __future__ import annotations

import base64
import binascii
import logging
import math

logger = logging.getLogger(__name__)

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Mapping, Optional

from peewee import (
    Field,
    DateField,
    BooleanField,
    IntegerField,
    FloatField,
    DoubleField,
    DecimalField,
    BigIntegerField,
    SmallIntegerField,
    ForeignKeyField,
)

from PySide6.QtCore import (
    Qt,
    Signal,
    QRect,
    QPoint,
    QDate,
    QSortFilterProxyModel,
    QRegularExpression,
    QByteArray,
    QTimer,
)
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
    QToolBar,
    QLineEdit,
    QCheckBox,
    QDateEdit,
    QLabel,
    QWidgetAction,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
)

from ui.base.table_controller import TableController
from ui.common.paginator import Paginator
from ui.common.styled_widgets import styled_button
from ui.common.date_utils import (
    clear_optional_date,
    configure_optional_date_edit,
    get_date_or_none,
)
from ui.common.multi_filter_proxy import ColumnFilterState
from ui import settings as ui_settings
from services.folder_utils import open_folder, copy_text_to_clipboard
from services.export_service import export_objects_to_csv
from database.models import Deal


class BaseTableView(QWidget):
    class _ProxyModel(QSortFilterProxyModel):
        def __init__(self, owner: "BaseTableView") -> None:
            super().__init__(owner)
            self._owner = owner

        def filterAcceptsRow(self, source_row: int, source_parent) -> bool:  # type: ignore[override]
            return self._owner._filter_accepts_row(source_row, source_parent)

        def headerData(self, section, orientation, role=Qt.DisplayRole):  # type: ignore[override]
            base = super().headerData(section, orientation, role)
            return self._owner._proxy_header_data(section, orientation, role, base)

    row_double_clicked = Signal(object)  # объект строки по двойному клику
    data_loaded = Signal(int)  # сигнал о загрузке данных (количество)
    # Соответствие индекса столбца полю модели или строковому пути.
    # Значение ``None`` скрывает фильтр.
    COLUMN_FIELD_MAP: dict[int, Field | str | None] = {}

    def _on_filters_changed(self, *args, **kwargs):
        """Безопасно обрабатывает изменение фильтров во время инициализации."""
        if hasattr(self, "toolbar"):
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
        self._settings_loaded = False
        self._block_pending_restore = False
        self._settings_restore_pending = False

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
        self._save_settings_timer = QTimer(self)
        self._save_settings_timer.setSingleShot(True)
        self._save_settings_timer.setInterval(250)
        self._save_settings_timer.timeout.connect(self.save_table_settings)
        self.splitter.splitterMoved.connect(self._schedule_save_table_settings)
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        self.splitter.addWidget(self.left_panel)
        self.outer_layout.addWidget(self.splitter)
        self.setLayout(self.outer_layout)

        # Фильтры на QToolBar
        checkbox_map = kwargs.get("checkbox_map") or {}
        checkbox_map.setdefault(
            "Показывать удалённые", lambda state: self._on_filters_changed()
        )

        self.date_filter_field = date_filter_field
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.left_layout.addWidget(self.toolbar)

        # Поле поиска
        self.search_edit = QLineEdit()
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setPlaceholderText("Поиск…")
        self.search_edit.textChanged.connect(self._on_filters_changed)
        self.toolbar.addWidget(self.search_edit)

        # Фильтр по дате
        if date_filter_field:
            self.date_from = QDateEdit()
            self.date_from.setCalendarPopup(True)
            self.date_from.setSpecialValueText("—")
            configure_optional_date_edit(self.date_from)
            self.date_from.dateChanged.connect(self._on_filters_changed)
            self.date_to = QDateEdit()
            self.date_to.setCalendarPopup(True)
            self.date_to.setSpecialValueText("—")
            configure_optional_date_edit(self.date_to)
            self.date_to.dateChanged.connect(self._on_filters_changed)
            self.toolbar.addWidget(QLabel("С:"))
            self.toolbar.addWidget(self.date_from)
            self.toolbar.addWidget(QLabel("По:"))
            self.toolbar.addWidget(self.date_to)

        # Чекбоксы
        self.checkboxes: dict[str, QCheckBox] = {}
        for label, callback in checkbox_map.items():
            box = QCheckBox(label)
            box.stateChanged.connect(callback)
            self.toolbar.addWidget(box)
            self.checkboxes[label] = box

        # Экспорт и сброс
        self.export_all_checkbox = QCheckBox("Экспортировать всё")
        export_action = self.toolbar.addAction("📤 Экспорт CSV")
        self.toolbar.addWidget(self.export_all_checkbox)
        export_action.triggered.connect(
            lambda: self.export_csv(
                all_rows=self.export_all_checkbox.isChecked()
            )
        )

        reset_action = self.toolbar.addAction("Сбросить")
        reset_action.triggered.connect(self._on_reset_filters)

        QShortcut("Ctrl+F", self, activated=self.focus_search)

        # Кнопки
        self.button_row = QHBoxLayout()
        self.button_row.setContentsMargins(0, 0, 0, 0)
        self.button_row.setSpacing(6)

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
        self.proxy = self._ProxyModel(self)
        self.proxy.setSortRole(Qt.UserRole)
        self.proxy.setDynamicSortFilter(True)
        self.table.setEditTriggers(QTableView.NoEditTriggers)
        self._column_filters: dict[int, ColumnFilterState] = {}
        self._column_filter_matchers: dict[int, Callable[[Any, Any], bool]] = {}
        self._column_filter_strings: dict[int, str] = {}

        self.table.setModel(self.proxy)
        self.proxy_model = self.proxy  # backward compatibility
        self.table.setSortingEnabled(True)

        header = self.table.horizontalHeader()
        header.setSectionsMovable(True)
        header.setSectionsClickable(True)
        header.sortIndicatorChanged.connect(self._on_sort_indicator_changed)
        header.sectionResized.connect(self._schedule_save_table_settings)
        header.sectionMoved.connect(self._schedule_save_table_settings)
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._on_header_section_clicked)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setAlternatingRowColors(True)
        header.setSectionResizeMode(QHeaderView.Interactive)
        self.table.resizeColumnsToContents()
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_menu)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        self.left_layout.addWidget(self.table)

        # Пагинация
        self.paginator = Paginator(on_prev=self.prev_page, on_next=self.next_page, per_page=self.per_page)
        self.paginator.per_page_changed.connect(self._on_per_page_changed)
        self.left_layout.addWidget(self.paginator)

    def apply_saved_filters(self) -> None:
        """Переустанавливает сохранённые фильтры столбцов в прокси-модель."""
        header = self.table.horizontalHeader()
        column_count = header.count() if header is not None else 0
        removed_invalid = False
        for column, state in list(self._column_filters.items()):
            if column < 0 or column >= column_count:
                self._column_filters.pop(column, None)
                self._column_filter_matchers.pop(column, None)
                self._column_filter_strings.pop(column, None)
                removed_invalid = True
                continue
            self._apply_column_filter(
                column,
                state,
                save_settings=False,
                trigger_filter=False,
            )
        if removed_invalid:
            self.proxy.invalidateFilter()

    # ------------------------------------------------------------------
    # Helpers for toolbar-based filters
    # ------------------------------------------------------------------
    def focus_search(self) -> None:
        """Устанавливает фокус на поле поиска."""
        self.search_edit.setFocus()

    def get_search_text(self) -> str:
        """Возвращает текст из поля поиска."""
        return self.search_edit.text().strip()

    def is_checked(self, label: str) -> bool:
        """Возвращает состояние чекбокса по метке."""
        box = self.checkboxes.get(label)
        return box.isChecked() if box else False

    def get_date_filter(self) -> dict[str, date] | None:
        """Возвращает диапазон дат из виджетов фильтра."""
        if not self.date_filter_field:
            return None
        d1 = get_date_or_none(getattr(self, "date_from", None))
        d2 = get_date_or_none(getattr(self, "date_to", None))
        if d1 or d2:
            return {self.date_filter_field: (d1, d2)}
        return None

    def clear_filters(self) -> None:
        """Сбрасывает состояние всех фильтров на панели."""
        self.search_edit.blockSignals(True)
        self.search_edit.clear()
        self.search_edit.blockSignals(False)

        for box in self.checkboxes.values():
            box.blockSignals(True)
            box.setChecked(False)
            box.blockSignals(False)

        if self.date_filter_field:
            for widget in (self.date_from, self.date_to):
                widget.blockSignals(True)
                clear_optional_date(widget)
                widget.blockSignals(False)

    def clear_column_filters(self) -> None:
        """Очищает сохранённые фильтры столбцов и сбрасывает их в прокси."""
        columns = list(self._column_filters.keys())
        for column in columns:
            self._apply_column_filter(
                column,
                None,
                save_settings=False,
                trigger_filter=False,
            )
        self._column_filters.clear()
        self._column_filter_matchers.clear()
        self._column_filter_strings.clear()

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

    def _on_reset_filters(self):
        if self.controller:
            # Сбрасываем фильтры столбцов до сохранения настроек в контроллере
            self.clear_column_filters()
            self.controller._on_reset_filters()
            return

        self.clear_filters()
        self.clear_column_filters()
        self.save_table_settings()
        self.on_filter_changed()

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
        self.load_table_settings()

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
        return self.proxy.mapToSource(view_index).row()

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
            try:
                open_folder(path)
            except Exception as exc:  # noqa: BLE001
                from ui.common.message_boxes import show_error

                show_error(str(exc))

    def open_selected_deal(self):
        """Открыть связанную сделку для выбранной строки."""
        deal = self.get_selected_deal()
        if not deal:
            return
        from ui.views.deal_detail import DealDetailView

        context = getattr(self, "_context", None)
        DealDetailView(deal, parent=self, context=context).exec()

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

        fields: list[Field | None] = []
        for i in visible_indices:
            if len(model_fields) > i:
                fields.append(model_fields[i])
            else:
                fields.append(column_map.get(i))

        # Заголовки берём из модели, если есть.
        try:
            headers = [self.model.headerData(i, Qt.Horizontal, Qt.DisplayRole) for i in visible_indices]
        except Exception:
            headers = None

        # Отфильтровываем колонки без соответствующих полей
        mask = [f is not None for f in fields]
        visible_indices = [i for i, keep in zip(visible_indices, mask) if keep]
        fields = [f for f in fields if f is not None]
        if headers is not None:
            headers = [h for h, keep in zip(headers, mask) if keep]

        if headers is not None and len(headers) != len(fields):
            logger.warning(
                "Количество заголовков и полей не совпадает: %d != %d",
                len(headers),
                len(fields),
            )
            min_len = min(len(headers), len(fields))
            headers = headers[:min_len]
            fields = fields[:min_len]

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
        def _copy_value() -> None:
            try:
                copy_text_to_clipboard(text)
            except Exception as exc:  # noqa: BLE001
                from ui.common.message_boxes import show_error

                show_error(str(exc))

        act_copy.triggered.connect(_copy_value)
        act_deal.triggered.connect(self.open_selected_deal)
        act_deal.setEnabled(bool(self.get_selected_deal()))
        act_folder.setEnabled(has_path)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Helpers for header filters
    # ------------------------------------------------------------------
    def _header_placeholder_text(self, column: int) -> str:
        header_text = ""
        source_model = getattr(self.proxy, "sourceModel", None)
        model = source_model() if callable(source_model) else None
        if model is not None:
            header_value = model.headerData(column, Qt.Horizontal, Qt.DisplayRole)
        else:
            header_value = self.table.model().headerData(column, Qt.Horizontal, Qt.DisplayRole)
        if header_value is None:
            return ""
        return str(header_value)

    def _resolve_field_by_name(self, name: str) -> Field | None:
        if not name:
            return None
        model_fields = getattr(self.model, "fields", None)
        if model_fields:
            for field in model_fields:
                if getattr(field, "name", None) == name:
                    return field
        model_class = getattr(self.controller, "model_class", None) or self.model_class
        if model_class is not None:
            meta = getattr(model_class, "_meta", None)
            meta_fields = getattr(meta, "fields", None)
            if isinstance(meta_fields, dict):
                candidate = meta_fields.get(name)
                if isinstance(candidate, Field):
                    return candidate
        return None

    def _get_field_for_column(self, column: int) -> Field | str | None:
        column_map = getattr(self, "COLUMN_FIELD_MAP", {})
        if column in column_map:
            mapped = column_map[column]
            if isinstance(mapped, str):
                resolved = self._resolve_field_by_name(mapped)
                if resolved is not None:
                    return resolved
            return mapped
        model_fields = getattr(self.model, "fields", None)
        if model_fields and 0 <= column < len(model_fields):
            return model_fields[column]
        return None

    @staticmethod
    def _is_date_field(field: Field | None) -> bool:
        return isinstance(field, DateField)

    @staticmethod
    def _is_boolean_field(field: Field | None) -> bool:
        return isinstance(field, BooleanField)

    def _is_integer_field(self, field: Field | None) -> bool:
        if not isinstance(field, Field) or isinstance(field, ForeignKeyField):
            return False
        return isinstance(field, (IntegerField, BigIntegerField, SmallIntegerField))

    def _is_numeric_field(self, field: Field | None) -> bool:
        if not isinstance(field, Field) or isinstance(field, ForeignKeyField):
            return False
        return isinstance(
            field,
            (
                IntegerField,
                BigIntegerField,
                SmallIntegerField,
                FloatField,
                DoubleField,
                DecimalField,
            ),
        )

    @staticmethod
    def _format_date_range_display(start: date | None, end: date | None) -> str:
        parts: list[str] = []
        if start:
            parts.append(start.strftime("%d.%m.%Y"))
        if end:
            parts.append(end.strftime("%d.%m.%Y"))
        return " — ".join(parts)

    @staticmethod
    def _numeric_is_clear(spinbox: QDoubleSpinBox | QSpinBox, value: float) -> bool:
        minimum = spinbox.minimum()
        if isinstance(spinbox, QDoubleSpinBox):
            return math.isclose(value, minimum, rel_tol=1e-9, abs_tol=1e-9)
        return int(value) == int(minimum)

    def _create_text_filter_widget(
        self,
        menu: QMenu,
        column: int,
        visual: int,
        state: Optional[ColumnFilterState],
    ) -> Callable[[], None]:
        line = QLineEdit(menu)
        line.setPlaceholderText(self._header_placeholder_text(column))
        current_text = ""
        if isinstance(state, ColumnFilterState) and state.type == "text":
            current_text = str(state.value or "")
        line.setText(current_text)
        action = QWidgetAction(menu)
        action.setDefaultWidget(line)
        menu.addAction(action)
        line.textChanged.connect(lambda text, v=visual: self._on_filter_text_changed(v, text))

        def clear() -> None:
            line.blockSignals(True)
            line.clear()
            line.blockSignals(False)
            self._on_filter_text_changed(visual, "")

        return clear

    def _create_date_filter_widget(
        self,
        menu: QMenu,
        column: int,
        state: Optional[ColumnFilterState],
    ) -> Callable[[], None]:
        container = QWidget(menu)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        start_edit = QDateEdit(container)
        start_edit.setCalendarPopup(True)
        configure_optional_date_edit(start_edit)
        end_edit = QDateEdit(container)
        end_edit.setCalendarPopup(True)
        configure_optional_date_edit(end_edit)
        layout.addWidget(start_edit)
        dash = QLabel("—", container)
        dash.setAlignment(Qt.AlignCenter)
        layout.addWidget(dash)
        layout.addWidget(end_edit)
        action = QWidgetAction(menu)
        action.setDefaultWidget(container)
        menu.addAction(action)

        value = state.value if isinstance(state, ColumnFilterState) and state.type == "date_range" else None
        start_iso = value.get("from") if isinstance(value, dict) else None
        end_iso = value.get("to") if isinstance(value, dict) else None

        for edit, iso in ((start_edit, start_iso), (end_edit, end_iso)):
            edit.blockSignals(True)
            if iso:
                qdate = QDate.fromString(str(iso), Qt.ISODate)
                if qdate.isValid():
                    edit.setDate(qdate)
                else:
                    clear_optional_date(edit)
            else:
                clear_optional_date(edit)
            edit.blockSignals(False)

        def update() -> None:
            start_date = get_date_or_none(start_edit)
            end_date = get_date_or_none(end_edit)
            if start_date and end_date and start_date > end_date:
                qdate = QDate(start_date.year, start_date.month, start_date.day)
                end_edit.blockSignals(True)
                end_edit.setDate(qdate)
                end_edit.blockSignals(False)
                end_date = start_date
            if start_date or end_date:
                value_dict = {
                    "from": start_date.isoformat() if start_date else None,
                    "to": end_date.isoformat() if end_date else None,
                }
                display = self._format_date_range_display(start_date, end_date)
                state_obj = ColumnFilterState("date_range", value_dict, display=display)
            else:
                state_obj = None
            self._apply_column_filter(column, state_obj)

        start_edit.dateChanged.connect(lambda *_: update())
        end_edit.dateChanged.connect(lambda *_: update())

        def clear() -> None:
            for widget in (start_edit, end_edit):
                widget.blockSignals(True)
                clear_optional_date(widget)
                widget.blockSignals(False)
            self._apply_column_filter(column, None)

        return clear

    def _create_boolean_filter_widget(
        self,
        menu: QMenu,
        column: int,
        state: Optional[ColumnFilterState],
    ) -> Callable[[], None]:
        combo = QComboBox(menu)
        combo.addItem("Все", None)
        combo.addItem("Да", True)
        combo.addItem("Нет", False)
        action = QWidgetAction(menu)
        action.setDefaultWidget(combo)
        menu.addAction(action)

        current_value = state.value if isinstance(state, ColumnFilterState) and state.type == "bool" else None
        index = 0
        for i in range(combo.count()):
            if combo.itemData(i) == current_value:
                index = i
                break
        combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(False)

        def on_changed(idx: int) -> None:
            value = combo.itemData(idx)
            if value is None:
                self._apply_column_filter(column, None)
                return
            display = "Да" if value else "Нет"
            self._apply_column_filter(
                column,
                ColumnFilterState("bool", bool(value), display=display),
            )

        combo.currentIndexChanged.connect(on_changed)

        def clear() -> None:
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
            self._apply_column_filter(column, None)

        return clear

    def _create_numeric_filter_widget(
        self,
        menu: QMenu,
        column: int,
        state: Optional[ColumnFilterState],
        field: Field,
    ) -> Callable[[], None]:
        is_integer = self._is_integer_field(field)
        if is_integer:
            spin: QDoubleSpinBox | QSpinBox = QSpinBox(menu)
            spin.setRange(-1_000_000_000, 1_000_000_000)
            spin.setSingleStep(1)
            meta = {"value_type": "int"}
        else:
            spin = QDoubleSpinBox(menu)
            spin.setRange(-1_000_000_000.0, 1_000_000_000.0)
            decimals = getattr(field, "decimal_places", 2)
            if not isinstance(decimals, int) or decimals < 0:
                decimals = 2
            spin.setDecimals(decimals)
            step = 10 ** (-decimals) if decimals else 1.0
            spin.setSingleStep(step)
            meta = {"value_type": "float"}
        spin.setKeyboardTracking(False)
        spin.setAccelerated(True)
        spin.setSpecialValueText("—")
        action = QWidgetAction(menu)
        action.setDefaultWidget(spin)
        menu.addAction(action)

        sentinel = spin.minimum()
        value = None
        if isinstance(state, ColumnFilterState) and state.type == "number":
            value = state.value
            meta.update(state.meta or {})

        spin.blockSignals(True)
        if value is None:
            spin.setValue(sentinel)
        else:
            try:
                if is_integer:
                    spin.setValue(int(value))
                else:
                    spin.setValue(float(value))
            except (TypeError, ValueError):
                spin.setValue(sentinel)
        spin.blockSignals(False)

        def on_changed(val: float) -> None:
            if self._numeric_is_clear(spin, val):
                self._apply_column_filter(column, None)
                return
            numeric_value = int(val) if is_integer else float(val)
            display = str(numeric_value)
            self._apply_column_filter(
                column,
                ColumnFilterState("number", numeric_value, display=display, meta=dict(meta)),
            )

        spin.valueChanged.connect(on_changed)

        def clear() -> None:
            spin.blockSignals(True)
            spin.setValue(sentinel)
            spin.blockSignals(False)
            self._apply_column_filter(column, None)

        return clear

    def _on_header_section_clicked(self, pos: QPoint) -> None:
        header = self.table.horizontalHeader()
        column = header.logicalIndexAt(pos)
        if column < 0:
            return
        visual = header.visualIndex(column)
        if visual < 0:
            return
        column_map = getattr(self, "COLUMN_FIELD_MAP", {})
        if column in column_map and column_map[column] is None:
            return

        field = self._get_field_for_column(column)
        state = self._column_filters.get(column)

        menu = QMenu(self)
        clear_callback: Optional[Callable[[], None]]
        if isinstance(field, Field) and self._is_date_field(field):
            clear_callback = self._create_date_filter_widget(menu, column, state)
        elif isinstance(field, Field) and self._is_boolean_field(field):
            clear_callback = self._create_boolean_filter_widget(menu, column, state)
        elif isinstance(field, Field) and self._is_numeric_field(field):
            clear_callback = self._create_numeric_filter_widget(menu, column, state, field)
        else:
            clear_callback = self._create_text_filter_widget(menu, column, visual, state)

        menu.addSeparator()
        clear_action = menu.addAction("Очистить фильтр")
        if clear_callback:
            clear_action.triggered.connect(clear_callback)
        else:
            clear_action.triggered.connect(lambda: self._apply_column_filter(column, None))
        pos_x = header.sectionViewportPosition(column)
        rect = QRect(pos_x, 0, header.sectionSize(column), header.height())
        menu.popup(header.mapToGlobal(rect.bottomLeft()))

    def _on_filter_text_changed(self, visual: int, text: str) -> None:
        header = self.table.horizontalHeader()
        logical = header.logicalIndex(visual)
        if logical < 0:
            return
        text = text.strip()
        state = ColumnFilterState("text", text) if text else None
        self._apply_column_filter(logical, state)

    def _apply_column_filter(
        self,
        column: int,
        state: ColumnFilterState | Mapping[str, Any] | str | None,
        *,
        save_settings: bool = True,
        trigger_filter: bool = True,
    ) -> None:
        normalized = self._normalize_filter_state(state)
        previous_state = self._column_filters.get(column)
        previous_display = self._column_filter_strings.get(column)

        if normalized is None or normalized.is_empty():
            self._column_filters.pop(column, None)
            self._column_filter_matchers.pop(column, None)
            self._column_filter_strings.pop(column, None)
        else:
            matcher = self._create_filter_matcher(normalized)
            if matcher is None:
                self._column_filters.pop(column, None)
                self._column_filter_matchers.pop(column, None)
                self._column_filter_strings.pop(column, None)
            else:
                self._column_filters[column] = normalized
                self._column_filter_matchers[column] = matcher
                display = normalized.display_text()
                if display:
                    self._column_filter_strings[column] = display
                else:
                    self._column_filter_strings.pop(column, None)

        new_state = self._column_filters.get(column)
        new_display = self._column_filter_strings.get(column)
        if previous_state != new_state or previous_display != new_display:
            self.proxy.headerDataChanged.emit(Qt.Horizontal, column, column)

        self.proxy.invalidateFilter()

        if save_settings:
            self.save_table_settings()
        if trigger_filter:
            self.on_filter_changed()

    def _filter_accepts_row(self, source_row: int, source_parent) -> bool:
        model = self.proxy.sourceModel()
        if model is None:
            return True
        if not self._column_filter_matchers:
            return True
        for column, matcher in self._column_filter_matchers.items():
            if matcher is None:
                continue
            index = model.index(source_row, column, source_parent)
            raw_value = model.data(index, Qt.UserRole)
            display_value = model.data(index, self.proxy.filterRole())
            if not matcher(raw_value, display_value):
                return False
        return True

    def _proxy_header_data(self, section, orientation, role, base_value):
        if orientation != Qt.Horizontal:
            return base_value
        if role == Qt.DisplayRole and section in self._column_filter_strings:
            base_text = "" if base_value is None else str(base_value)
            return f"{base_text} ⏷" if base_text else "⏷"
        if role == Qt.ToolTipRole and section in self._column_filter_strings:
            base = base_value
            if not base:
                source_model = self.proxy.sourceModel()
                if source_model is not None:
                    base = source_model.headerData(section, orientation, Qt.DisplayRole)
            filter_text = self._column_filter_strings.get(section, "")
            if base:
                return f"{base}\nФильтр: {filter_text}"
            return f"Фильтр: {filter_text}"
        return base_value

    def _normalize_filter_state(
        self,
        state: ColumnFilterState | Mapping[str, Any] | str | None,
    ) -> ColumnFilterState | None:
        if state is None:
            return None
        if isinstance(state, ColumnFilterState):
            return state
        if isinstance(state, str):
            text = state.strip()
            if not text:
                return None
            return ColumnFilterState("text", text)
        return ColumnFilterState.from_dict(state)

    def _create_filter_matcher(
        self, state: ColumnFilterState
    ) -> Callable[[Any, Any], bool] | None:
        if state.type == "text":
            text = str(state.value or "").strip()
            if not text:
                return None
            options = (
                QRegularExpression.CaseInsensitiveOption
                if self.proxy.filterCaseSensitivity() == Qt.CaseInsensitive
                else QRegularExpression.NoPatternOption
            )
            esc = QRegularExpression.escape(text)
            pattern = f".*{esc}.*"
            regex = QRegularExpression(pattern, options)
            return lambda _raw, display: regex.match(
                "" if display is None else str(display)
            ).hasMatch()

        if state.type == "bool":
            desired = state.value
            if desired is None:
                return None
            bool_value = bool(desired)

            def matcher(raw: Any, _display: Any) -> bool:
                if raw is None:
                    return False
                if isinstance(raw, bool):
                    return raw is bool_value
                if isinstance(raw, (int, float)):
                    return bool(raw) is bool_value
                if isinstance(raw, str):
                    lowered = raw.lower()
                    if lowered in {"true", "1", "yes", "да"}:
                        return bool_value is True
                    if lowered in {"false", "0", "no", "нет"}:
                        return bool_value is False
                return False

            return matcher

        if state.type == "date_range" and isinstance(state.value, Mapping):
            start = self._parse_iso_date(state.value.get("from"))
            end = self._parse_iso_date(state.value.get("to"))
            if start is None and end is None:
                return None

            def matcher(raw: Any, _display: Any) -> bool:
                current = self._coerce_to_date(raw)
                if current is None:
                    return False
                if start and current < start:
                    return False
                if end and current > end:
                    return False
                return True

            return matcher

        if state.type == "number":
            meta = state.meta or {}
            value_type = meta.get("value_type")
            target = self._to_number(state.value, value_type)
            if target is None:
                return None

            def matcher(raw: Any, _display: Any) -> bool:
                current = self._to_number(raw, value_type)
                if current is None:
                    return False
                if value_type == "int":
                    return int(current) == int(target)
                return math.isclose(float(current), float(target), rel_tol=1e-9, abs_tol=1e-9)

            return matcher

        text = str(state.value or "").strip()
        if not text:
            return None
        options = (
            QRegularExpression.CaseInsensitiveOption
            if self.proxy.filterCaseSensitivity() == Qt.CaseInsensitive
            else QRegularExpression.NoPatternOption
        )
        esc = QRegularExpression.escape(text)
        pattern = f".*{esc}.*"
        regex = QRegularExpression(pattern, options)
        return lambda _raw, display: regex.match(
            "" if display is None else str(display)
        ).hasMatch()

    @staticmethod
    def _parse_iso_date(value: Any) -> date | None:
        if value in (None, ""):
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, QDate):
            return value.toPython()
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _coerce_to_date(value: Any) -> date | None:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, QDate):
            return value.toPython()
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _to_number(value: Any, value_type: Optional[str]) -> float | None:
        if value is None:
            return None
        if value_type == "int":
            try:
                return float(int(value))
            except (TypeError, ValueError):
                return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

    def _on_sort_indicator_changed(self, column: int, order: Qt.SortOrder):
        """Сохраняет текущую сортировку таблицы."""
        if not self._settings_loaded:
            self._block_pending_restore = True
        self.current_sort_column = column
        self.current_sort_order = order
        self.save_table_settings()

    def _schedule_save_table_settings(self, *_):
        self._save_settings_timer.start()

    def save_table_settings(self):
        """Сохраняет настройки сортировки и ширины колонок."""
        if not self._settings_loaded:
            return

        header = self.table.horizontalHeader()
        widths = {i: header.sectionSize(i) for i in range(header.count())}
        hidden = [i for i in range(header.count()) if self.table.isColumnHidden(i)]
        order = [header.visualIndex(i) for i in range(header.count())]
        filters = {
            str(column): state.to_dict()
            for column, state in self._column_filters.items()
        }
        settings = {
            "sort_column": self.current_sort_column,
            "sort_order": self.current_sort_order.value,
            "column_widths": widths,
            "hidden_columns": hidden,
            "column_order": order,
            "column_filters": filters,
            "per_page": self.per_page,
        }
        settings["splitter_state"] = base64.b64encode(
            bytes(self.splitter.saveState())
        ).decode("ascii")
        ui_settings.set_table_settings(self.settings_id, settings)

    def load_table_settings(self):
        """Применяет сохранённые настройки, если они есть."""
        self._settings_restore_pending = False
        header = self.table.horizontalHeader()
        saved = ui_settings.get_table_settings(self.settings_id)
        if not saved:
            if self.splitter.count() > 1:
                self.splitter.setStretchFactor(0, 3)
                self.splitter.setStretchFactor(1, 2)
            self._settings_loaded = True
            return
        splitter_restored = False
        encoded_splitter = saved.get("splitter_state")
        if encoded_splitter:
            try:
                decoded = base64.b64decode(encoded_splitter)
            except (TypeError, ValueError, binascii.Error):
                decoded = b""
            if decoded:
                splitter_restored = self.splitter.restoreState(QByteArray(decoded))
        if not splitter_restored and self.splitter.count() > 1:
            self.splitter.setStretchFactor(0, 3)
            self.splitter.setStretchFactor(1, 2)
        column = saved.get("sort_column")
        order = saved.get("sort_order")
        if not self._block_pending_restore and column is not None and order is not None:
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
        saved_filters = saved.get("column_filters", {})
        previous_columns = set(self._column_filter_strings.keys())
        self._column_filters = {}
        self._column_filter_matchers = {}
        self._column_filter_strings = {}
        cleared_columns: set[int] = set()
        invalidated = False
        if isinstance(saved_filters, dict):
            for col, raw_state in saved_filters.items():
                try:
                    col_int = int(col)
                except (TypeError, ValueError):
                    continue
                if col_int >= header.count():
                    continue
                state = self._normalize_filter_state(raw_state)
                if state is None or state.is_empty():
                    cleared_columns.add(col_int)
                    continue
                self._apply_column_filter(
                    col_int,
                    state,
                    save_settings=False,
                    trigger_filter=False,
                )
                invalidated = True
        current_columns = set(self._column_filter_strings.keys())
        for column in (previous_columns | cleared_columns) - current_columns:
            if 0 <= column < header.count():
                self.proxy.headerDataChanged.emit(Qt.Horizontal, column, column)
        if not invalidated and (previous_columns or cleared_columns):
            self.proxy.invalidateFilter()
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
        self._block_pending_restore = False
        self._settings_loaded = True

    def closeEvent(self, event):
        self.save_table_settings()
        super().closeEvent(event)
