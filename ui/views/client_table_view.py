# ui/views/client_table_view.py

from database.models import Client
from services.client_service import (
    build_client_query,
    get_clients_page,
    mark_client_deleted,
    mark_clients_deleted,
)
from services.folder_utils import open_folder
from ui.base.base_table_view import BaseTableView
from PySide6.QtWidgets import QAbstractItemView
from ui.common.message_boxes import confirm, show_error
from ui.common.styled_widgets import styled_button
from ui.forms.client_form import ClientForm
from ui.views.client_detail_view import ClientDetailView


class ClientTableView(BaseTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model_class = Client  # или Client, Policy и т.д.
        self.form_class = ClientForm  # соответствующая форма
        self.form_class = ClientForm
        # разрешаем выбор нескольких строк для массовых действий
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.row_double_clicked.connect(self.open_detail)
        folder_btn = styled_button("📂 Папка", tooltip="Открыть папку клиента")
        folder_btn.clicked.connect(self.open_selected_folder)
        # Добавляем перед растягивающим элементом
        self.button_row.insertWidget(self.button_row.count() - 1, folder_btn)
        self.load_data()  # загрузка данных при инициализации

    def get_filters(self) -> dict:
        """
        Собирает фильтры:
         - текстовый поиск
         - флаг 'Показывать удалённые'
        """
        filters = super().get_filters()
        return filters

    def load_data(self):
        # 1) читаем фильтры
        filters = self.get_filters()
        
        # 2) загружаем страницу и считаем общее количество
        items = get_clients_page(self.page, self.per_page, **filters)
        total = build_client_query(**filters).count()

        # 3) обновляем таблицу и пагинатор
        self.set_model_class_and_items(Client, list(items), total_count=total)

    def get_selected(self):
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        source_row = self.proxy_model.mapToSource(index).row()
        return self.model.get_item(source_row)

    def get_selected_multiple(self):
        indexes = self.table.selectionModel().selectedRows()
        return [self.model.get_item(self.proxy_model.mapToSource(i).row()) for i in indexes]

    def delete_selected(self):
        clients = self.get_selected_multiple()
        if not clients:
            return
        if len(clients) == 1:
            message = f"Удалить клиента {clients[0].name}?"
        else:
            message = f"Удалить {len(clients)} клиент(ов)?"
        if confirm(message):
            try:
                if len(clients) == 1:
                    mark_client_deleted(clients[0].id)
                else:
                    ids = [c.id for c in clients]
                    mark_clients_deleted(ids)
                self.refresh()
            except Exception as e:
                show_error(str(e))

    def open_detail(self, client: Client):
        if self.use_inline_details:
            self.set_detail_widget(ClientDetailView(client, parent=self))
        else:
            dlg = ClientDetailView(client, parent=self)
            dlg.exec()

    def open_selected_folder(self):
        client = self.get_selected()
        if not client:
            return
        path = client.drive_folder_path or client.drive_folder_link
        open_folder(path, parent=self)
