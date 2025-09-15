from ui.base.table_controller import TableController
from database.models import Client
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

