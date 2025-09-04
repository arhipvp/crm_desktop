from ui.base.table_controller import TableController
from database.models import Client
from PySide6.QtCore import Qt
from .client_service import (
    build_client_query,
    get_clients_page_dto,
    delete_clients,
)
from .dto import ClientDTO


class ClientTableController(TableController):
    """Контроллер таблицы клиентов, работающий с DTO."""

    def __init__(self, view):
        super().__init__(
            view,
            model_class=Client,
            get_page_func=get_clients_page_dto,
            get_total_func=lambda **f: build_client_query(**f).count(),
        )

    def delete_clients(self, clients: list[ClientDTO]) -> None:
        delete_clients(clients)

    def get_filters(self) -> dict:
        filters = super().get_filters()
        model = getattr(self.view, "model", None)
        field_name = "name"
        if model and 0 <= self.view.current_sort_column < len(model.fields):
            field_name = model.fields[self.view.current_sort_column].name
        filters.update(
            order_by=field_name,
            order_dir=(
                "desc"
                if self.view.current_sort_order == Qt.DescendingOrder
                else "asc"
            ),
        )
        return filters
