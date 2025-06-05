# ui/views/client_table_view.py

from database.models import Client
from services.client_service import (
    build_client_query,
    get_clients_page,
    mark_client_deleted,
)
from services.folder_utils import open_folder
from ui.base.base_table_view import BaseTableView
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
        return {
            "search_text": self.filter_controls.get_search_text(),
            "show_deleted": self.filter_controls.is_checked("Показывать удалённые"),
        }

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

    def delete_selected(self):
        client = self.get_selected()
        if not client:
            return
        if confirm(f"Удалить клиента {client.name}?"):
            try:
                mark_client_deleted(client.id)
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
