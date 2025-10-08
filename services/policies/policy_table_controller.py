from typing import Any, Iterable, Sequence

from database.models import Policy
from ui.base.table_controller import TableController

from .policy_app_service import policy_app_service
from .dto import PolicyRowDTO


class PolicyTableController(TableController):
    """Контроллер таблицы полисов, работающий с DTO."""

    def __init__(self, view, service=policy_app_service, *, filter_func=None):
        self.service = service
        self._pending_total: int | None = None
        super().__init__(
            view,
            model_class=PolicyRowDTO,
            get_page_func=self._get_page,
            get_total_func=self._get_total,
            filter_func=filter_func,
        )

    def delete_policies(self, policies: list[PolicyRowDTO]) -> list[int]:
        ids = [policy.id for policy in policies]
        context = getattr(self.view, "_context", None)
        gateway = getattr(context, "drive_gateway", None) if context else None
        return self.service.mark_deleted(ids, gateway=gateway)

    def get_policies_by_ids(
        self, policy_ids: Sequence[int], *, as_dto: bool = False
    ) -> dict[int, Policy | PolicyRowDTO]:
        """Получить полисы по идентификаторам через фасад."""

        return self.service.get_policies_by_ids(policy_ids, as_dto=as_dto)

    def update_policy_field(self, policy_id: int, field: str, value: Any) -> PolicyRowDTO:
        """Обновить отдельное поле полиса через фасад приложения."""

        return self.service.update_policy_field(policy_id, field, value)

    def _get_page(self, page: int, per_page: int, **filters):
        policies, total = self.service.get_page_with_total(
            page,
            per_page,
            **filters,
        )
        self._pending_total = total
        return policies

    def _get_total(self, **filters):
        if self._pending_total is not None:
            total = self._pending_total
            self._pending_total = None
            return total
        return self.service.count(**filters)

    def _create_table_model(
        self, items: Iterable[PolicyRowDTO], model_class
    ):
        factory = getattr(self.view, "create_table_model", None)
        if callable(factory):
            return factory(items, model_class)
        return super()._create_table_model(items, model_class)

    def get_distinct_values(
        self, column_key: str, *, column_field: Any | None = None
    ) -> list[dict[str, Any]] | None:
        filters = self.get_filters()
        column_filters = dict(filters.get("column_filters") or {})
        removed = False
        if column_field is not None and column_field in column_filters:
            column_filters.pop(column_field, None)
            removed = True
        if not removed:
            column_filters.pop(column_key, None)
        filters["column_filters"] = column_filters
        try:
            return self.service.get_distinct_values(
                column_key, column_field=column_field, filters=filters
            )
        except TypeError:
            return self.service.get_distinct_values(column_key, filters=filters)


__all__ = ["PolicyTableController"]
