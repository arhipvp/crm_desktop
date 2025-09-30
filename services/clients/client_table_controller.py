from ui.base.table_controller import TableController

from .client_app_service import client_app_service
from .dto import ClientDTO


class ClientTableController(TableController):
    """Контроллер таблицы клиентов, работающий с DTO."""

    def __init__(self, view, service=client_app_service):
        self.service = service
        super().__init__(
            view,
            model_class=ClientDTO,
            get_page_func=self._get_page,
            get_total_func=self._get_total,
        )

    def delete_clients(self, clients: list[ClientDTO]) -> None:
        ids = [client.id for client in clients]
        self.service.delete_many(ids)

    def _get_page(self, page: int, per_page: int, **filters):
        return self.service.get_page(page, per_page, **filters)

    def _get_total(self, **filters):
        return self.service.count(**filters)

