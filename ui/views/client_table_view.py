# ui/views/client_table_view.py

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView

from core.app_context import AppContext
from services.clients.client_app_service import (
    ClientMergeError,
    ClientNotFoundError,
    client_app_service,
)
from services.clients.client_table_controller import ClientTableController
from services.clients.dto import ClientDTO
from services.folder_utils import open_folder
from ui.base.base_table_view import BaseTableView
from ui.common.message_boxes import confirm, show_error, show_info
from ui.common.styled_widgets import styled_button
from ui.forms.client_form import ClientForm
from ui.forms.client_merge_dialog import ClientMergeDialog
from ui.views.client_detail_view import ClientDetailView


class ClientTableView(BaseTableView):
    def __init__(
        self,
        parent=None,
        *,
        context: AppContext | None = None,
        controller: ClientTableController | None = None,
        service=client_app_service,
    ):
        self._context = context
        controller = controller or ClientTableController(
            self, service=service or client_app_service
        )
        super().__init__(parent, form_class=ClientForm, controller=controller)
        # разрешаем выбор нескольких строк для массовых действий
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.row_double_clicked.connect(self.open_detail)
        self.table.horizontalHeader().sortIndicatorChanged.connect(
            self.on_sort_changed
        )
        folder_btn = styled_button("📂 Папка", tooltip="Открыть папку клиента")
        folder_btn.clicked.connect(self.open_selected_folder)
        self.merge_btn = styled_button(
            "Объединить",
            tooltip="Объединить выбранных клиентов",
        )
        self.merge_btn.setEnabled(False)
        self.merge_btn.clicked.connect(self.merge_selected_clients)
        # Добавляем перед растягивающим элементом
        self.button_row.insertWidget(self.button_row.count() - 1, folder_btn)
        self.button_row.insertWidget(self.button_row.count() - 1, self.merge_btn)
        selection_model = self.table.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self.on_selection_changed)
        self.update_merge_button_state()
        self.load_data()

    def get_selected(self):
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        source_row = self.proxy.mapToSource(index).row()
        return self.model.get_item(source_row)

    def get_selected_multiple(self):
        indexes = self.table.selectionModel().selectedRows()
        return [self.model.get_item(self.proxy.mapToSource(i).row()) for i in indexes]

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
                self.controller.delete_clients(clients)
                self.refresh()
            except Exception as e:
                show_error(str(e))

    def open_detail(self, client: ClientDTO):
        try:
            full_client = client_app_service.get_detail(client.id)
        except ClientNotFoundError:
            show_error("Клиент не найден")
            return

        if self.use_inline_details:
            self.set_detail_widget(ClientDetailView(full_client, parent=self))
        else:
            dlg = ClientDetailView(full_client, parent=self)
            dlg.exec()

    def open_selected_folder(self):
        client = self.get_selected()
        if not client:
            return
        path = client.drive_folder_path or client.drive_folder_link
        try:
            open_folder(path)
        except Exception as exc:  # noqa: BLE001
            show_error(str(exc))

    def on_sort_changed(self, column: int, order: Qt.SortOrder):
        """Обновляет параметры сортировки и перезагружает таблицу."""
        self.current_sort_column = column
        self.current_sort_order = order
        self.load_data()

    # ------------------------------------------------------------------
    # Объединение клиентов
    # ------------------------------------------------------------------

    def on_selection_changed(self, *_args):
        self.update_merge_button_state()

    def update_merge_button_state(self) -> None:
        selection_model = self.table.selectionModel()
        if not selection_model:
            self.merge_btn.setEnabled(False)
            return
        self.merge_btn.setEnabled(len(selection_model.selectedRows()) >= 2)

    def merge_selected_clients(self) -> None:
        clients = self.get_selected_multiple()
        if len(clients) < 2:
            return

        try:
            full_clients = client_app_service.get_merge_candidates([c.id for c in clients])
        except ClientMergeError as exc:
            show_error(str(exc))
            return

        try:
            dialog = ClientMergeDialog(full_clients, parent=self)
        except Exception as exc:  # ValueError и др. ошибки инициализации
            show_error(str(exc))
            return

        if not dialog.exec():
            return

        primary_id = dialog.get_primary_client_id()
        duplicate_ids = dialog.get_duplicate_client_ids()
        final_values = dialog.get_final_values()

        try:
            client_app_service.merge(primary_id, duplicate_ids, final_values)
        except ClientMergeError as exc:
            show_error(str(exc))
            return

        self.refresh()
        self.merge_btn.setEnabled(False)
        show_info("Клиенты успешно объединены")
