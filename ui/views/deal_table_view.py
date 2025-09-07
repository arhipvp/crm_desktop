from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QShortcut
from PySide6.QtWidgets import QMenu
from PySide6.QtWidgets import QMenu, QLineEdit, QComboBox, QHBoxLayout

from ui.base.base_table_model import BaseTableModel

from database.models import Deal, Client, Executor, DealStatus
from services.deal_service import build_deal_query, get_deals_page, mark_deal_deleted
from ui.base.base_table_view import BaseTableView
from ui.common.message_boxes import confirm, show_error
from ui.forms.deal_form import DealForm
from ui.views.deal_detail import DealDetailView


class DealTableModel(BaseTableModel):
    def __init__(self, objects, model_class, parent=None):
        super().__init__(objects, model_class, parent)

        # сохраняем полный список объектов для последующей фильтрации
        self._all_objects = list(objects)

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

        # параметры быстрого фильтра
        self._quick_text = ""
        self._quick_status: str | None = None

    def columnCount(self, parent=None):
        return len(self.fields) + len(self.virtual_fields)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        obj = self.objects[index.row()]
        if role == Qt.FontRole and getattr(obj, "is_deleted", False):
            font = QFont()
            font.setStrikeOut(True)
            return font
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

    # --- Быстрый фильтр -------------------------------------------------
    def apply_quick_filter(self, text: str = "", status: str | None = None) -> None:
        """Фильтрует ``self.objects`` по строке и статусу.

        Parameters:
            text: Подстрока для поиска в описании и имени клиента.
            status: Статус сделки или ``None`` для всех.
        """

        self._quick_text = text.lower()
        self._quick_status = status

        def matches(obj) -> bool:
            if self._quick_text:
                haystack = " ".join(
                    [
                        getattr(obj.client, "name", ""),
                        getattr(obj, "description", ""),
                        getattr(obj, "status", ""),
                    ]
                ).lower()
                if self._quick_text not in haystack:
                    return False
            if self._quick_status:
                if getattr(obj, "status", None) != self._quick_status:
                    return False
            return True

        self.objects = [obj for obj in self._all_objects if matches(obj)]
        self.layoutChanged.emit()


class DealTableView(BaseTableView):
    COLUMN_FIELD_MAP = {
        0: Deal.reminder_date,
        1: Client.name,
        2: Deal.status,
        3: Deal.description,
        4: Deal.calculations,
        5: Deal.start_date,
        6: Deal.is_closed,
        7: Deal.closed_reason,
        8: Executor.full_name,
    }

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

        # --- быстрый фильтр по строке и статусу -----------------------
        self.quick_filter_edit = QLineEdit()
        self.quick_filter_edit.setPlaceholderText("Поиск...")
        self.status_filter = QComboBox()
        self.status_filter.addItem("Все", None)
        for st in DealStatus:
            self.status_filter.addItem(st.value, st.value)

        quick_layout = QHBoxLayout()
        quick_layout.addWidget(self.quick_filter_edit)
        quick_layout.addWidget(self.status_filter)

        index = self.left_layout.indexOf(self.table)
        self.left_layout.insertLayout(index, quick_layout)

        self.quick_filter_edit.textChanged.connect(self.apply_quick_filter)
        self.status_filter.currentIndexChanged.connect(self.apply_quick_filter)

        self.sort_field = "reminder_date"
        self.sort_order = "asc"  # 'asc' or 'desc'
        self.default_sort_field = "reminder_date"

        self.table.horizontalHeader().sortIndicatorChanged.connect(
            self.on_sort_changed
        )
        self.row_double_clicked.connect(self.open_detail)

        QShortcut("Return", self.table, activated=self.open_detail)
        QShortcut("Ctrl+E", self.table, activated=self.edit_selected)
        QShortcut("Delete", self.table, activated=self.delete_selected)
        QShortcut("Ctrl+D", self.table, activated=self.duplicate_selected)

        self.load_data()

    # Ensure search/filters/pagination call our loader (not TableController)
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

    def _on_per_page_changed(self, per_page: int):
        self.per_page = per_page
        self.page = 1
        try:
            self.save_table_settings()
        except Exception:
            pass
        self.load_data()

    def _on_column_filter_changed(self, column: int, text: str):
        self.on_filter_changed()
        try:
            self.save_table_settings()
        except Exception:
            pass

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
        self.column_filters.set_headers(
            headers, column_field_map=self.COLUMN_FIELD_MAP
        )

        # какой столбец сейчас является полем сортировки?
        col = self.get_column_index(self.sort_field)
        order = Qt.DescendingOrder if self.sort_order == "desc" else Qt.AscendingOrder

        # показываем пользователю правильный индикатор сортировки
        self.table.horizontalHeader().setSortIndicator(col, order)
        # и не даём базовому классу перезаписывать порядок

        # применяем быстрый фильтр к новым данным
        self.apply_quick_filter()

    def get_selected(self):
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        return self.model.get_item(self._source_row(index))

    def apply_quick_filter(self):
        if not getattr(self, "model", None):
            return
        text = self.quick_filter_edit.text().strip()
        status = self.status_filter.currentData()
        self.model.apply_quick_filter(text, status)

    def add_new(self):
        form = DealForm()
        if form.exec():
            self.refresh()
            if form.instance:
                dlg = DealDetailView(form.instance, parent=self)
                dlg.exec()

    def duplicate_selected(self, _=None):
        deal = self.get_selected()
        if not deal:
            return
        form = DealForm()
        form.fill_from_obj(deal)
        if "is_closed" in form.fields:
            form.fields["is_closed"].setChecked(False)
        if "closed_reason" in form.fields:
            form.fields["closed_reason"].setText("")
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

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        act_open = menu.addAction("Открыть сделку")
        act_edit = menu.addAction("Редактировать")
        act_folder = menu.addAction("Открыть папку сделки")
        act_copy = menu.addAction("Копировать телефон клиента")
        act_whatsapp = menu.addAction("Открыть WhatsApp")

        action = menu.exec(event.globalPos())
        if action == act_open:
            self.open_detail()
        elif action == act_edit:
            self.edit_selected()
        elif action == act_folder:
            self._open_folder()
        elif action == act_copy:
            self._copy_client_phone()
        elif action == act_whatsapp:
            self._open_whatsapp()

    def _open_folder(self):
        deal = self.get_selected()
        if not deal:
            return
        from services.folder_utils import open_folder

        open_folder(
            getattr(deal, "drive_folder_path", None) or deal.drive_folder_link,
            parent=self,
        )

    def _copy_client_phone(self):
        deal = self.get_selected()
        if not deal or not getattr(deal, "client", None) or not deal.client.phone:
            show_error("Не указан телефон клиента")
            return
        from services.folder_utils import copy_text_to_clipboard

        copy_text_to_clipboard(deal.client.phone, parent=self)

    def _open_whatsapp(self):
        deal = self.get_selected()
        if not deal or not getattr(deal, "client", None):
            return
        phone = deal.client.phone
        if not phone:
            show_error("Не указан телефон клиента")
            return
        from services.clients import (
            format_phone_for_whatsapp,
            open_whatsapp,
        )

        open_whatsapp(format_phone_for_whatsapp(phone))

    def on_sort_changed(self, column: int, order: Qt.SortOrder):
        """Refresh data after the user changed sort order."""
        if not self.model or column >= len(self.model.fields):
            return

        self.current_sort_column = column
        self.current_sort_order = order
        self.sort_field = self.model.fields[column].name
        self.sort_order = "desc" if order == Qt.DescendingOrder else "asc"
        self.refresh()
