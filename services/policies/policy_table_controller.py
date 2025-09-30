from ui.base.table_controller import TableController

from .policy_app_service import policy_app_service
from .dto import PolicyRowDTO


class PolicyTableController(TableController):
    """Контроллер таблицы полисов, работающий с DTO."""

    def __init__(self, view, service=policy_app_service, *, filter_func=None):
        self.service = service
        super().__init__(
            view,
            model_class=PolicyRowDTO,
            get_page_func=self._get_page,
            get_total_func=self._get_total,
            filter_func=filter_func,
        )

    def delete_policies(self, policies: list[PolicyRowDTO]) -> list[int]:
        ids = [policy.id for policy in policies]
        return self.service.mark_deleted(ids)

    def _get_page(self, page: int, per_page: int, **filters):
        return self.service.get_page(page, per_page, **filters)

    def _get_total(self, **filters):
        return self.service.count(**filters)


__all__ = ["PolicyTableController"]
