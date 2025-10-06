import logging
from datetime import date, datetime

from typing import Any

from peewee import Field, prefetch
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import QHeaderView, QAbstractItemView

from core.app_context import AppContext

from database.models import Client, Income, Payment, Policy, Deal, Executor, DealExecutor
from services.income_service import (
    build_income_query,
    mark_income_deleted,
    mark_incomes_deleted,
    get_incomes_page,
)
from ui.base.base_table_model import BaseTableModel
from ui.base.base_table_view import BaseTableView
from ui.base.table_controller import TableController
from ui.common.message_boxes import confirm, show_error
from ui.forms.income_form import IncomeForm


logger = logging.getLogger(__name__)


class IncomeTableController(TableController):
    def __init__(self, view) -> None:
        super().__init__(view, model_class=Income)

    def get_filters(self) -> dict:
        filters = super().get_filters()
        filters["include_received"] = bool(
            self.view.is_checked("Показывать выплаченные")
        )
        deal_id = getattr(self.view, "deal_id", None)
        if deal_id is not None:
            filters["deal_id"] = deal_id
        date_range = filters.pop("received_date", None)
        if date_range:
            filters["received_date_range"] = date_range
        return filters

    def get_distinct_values(
        self, column_key: str, *, column_field: Any | None = None
    ) -> list[dict[str, Any]]:
        filters = self.get_filters()
        column_filters = dict(filters.get("column_filters") or {})
        removed = False
        if column_field is not None and column_field in column_filters:
            column_filters.pop(column_field, None)
            removed = True
        if not removed:
            column_filters.pop(column_key, None)
        filters["column_filters"] = column_filters

        search_text = str(filters.get("search_text") or "")
        show_deleted = bool(filters.get("show_deleted"))
        include_received = bool(filters.get("include_received", True))
        received_range = filters.get("received_date_range")
        deal_id = filters.get("deal_id")
        join_executor = column_field is Executor.full_name

        query = build_income_query(
            search_text=search_text,
            show_deleted=show_deleted,
            include_received=include_received,
            received_date_range=received_range,
            column_filters=column_filters,
            deal_id=deal_id,
            join_executor=join_executor,
        )

        if isinstance(column_field, Field):
            target_field = column_field
        else:
            field_map: dict[str, Field] = {
                "policy_number": Policy.policy_number,
                "deal_description": Deal.description,
                "client_name": Client.name,
                "sales_channel": Policy.sales_channel,
                "start_date": Policy.start_date,
                "amount": Income.amount,
                "payment_date": Payment.payment_date,
                "received_date": Income.received_date,
            }
            target_field = field_map.get(column_key)

        if target_field is None:
            return []

        values_query = (
            query.select(target_field)
            .where(target_field.is_null(False))
            .distinct()
            .order_by(target_field.asc())
        )

        values = [
            {"value": value, "display": value}
            for (value,) in values_query.tuples()
        ]

        if (
            query.select(target_field)
            .where(target_field.is_null(True))
            .limit(1)
            .exists()
        ):
            values.insert(0, {"value": None, "display": "—"})

        return values


class IncomeTableModel(BaseTableModel):
    VIRTUAL_FIELDS = [
        "policy_number",
        "deal_desc",
        "client_name",
        "sales_channel",
        "policy_start",
        "payment_amount",
        "payment_date",
        "amount",
        "received",
        "executor",
    ]

    def __init__(self, objects, model_class, parent=None):
        super().__init__(objects, model_class, parent)
        self.fields = []  # отключаем стандартные поля модели

        self.virtual_fields = self.VIRTUAL_FIELDS
        self.headers = [
            "Полис",
            "Сделка",
            "Клиент",
            "Канал продаж",
            "Дата начала",
            "Сумма платежа",
            "Дата платежа",
            "Сумма комиссии",
            "Дата получения",
            "Исполнитель",
        ]

    def columnCount(self, parent=None):
        return len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        obj = self.objects[index.row()]
        col = index.column()

        def to_qdate(value):
            if isinstance(value, QDate):
                return value
            if isinstance(value, datetime):
                value = value.date()
            if isinstance(value, date):
                return QDate(value.year, value.month, value.day)
            return None

        payment = getattr(obj, "payment", None)
        policy = getattr(payment, "policy", None) if payment else None
        deal = getattr(policy, "deal", None) if policy else None

        policy_number = policy.policy_number if policy else None
        deal_description = deal.description if deal else None
        client_name = policy.client.name if policy and policy.client else None
        sales_channel = policy.sales_channel if policy and policy.sales_channel else None
        policy_start_date = policy.start_date if policy and policy.start_date else None
        policy_start_qdate = to_qdate(policy_start_date)
        payment_amount = payment.amount if payment else None
        payment_date = payment.payment_date if payment and payment.payment_date else None
        payment_qdate = to_qdate(payment_date)
        income_amount = obj.amount if obj.amount is not None else None
        received_date = obj.received_date
        received_qdate = to_qdate(received_date)
        executor_name = None
        if deal and getattr(deal, "executors", None):
            ex = deal.executors[0].executor
            executor_name = ex.full_name if ex else None

        raw_values = {
            0: policy_number,
            1: deal_description,
            2: client_name,
            3: sales_channel,
            4: policy_start_qdate,
            5: payment_amount,
            6: payment_qdate,
            7: income_amount,
            8: received_qdate,
            9: executor_name,
        }

        if role == Qt.UserRole:
            return raw_values.get(col)

        if role != Qt.DisplayRole:
            return None

        if col == 0:
            return policy_number or "—"
        elif col == 1:
            return deal_description or "—"
        elif col == 2:
            return client_name or "—"
        elif col == 3:
            return sales_channel or "—"
        elif col == 4:
            return (
                policy_start_date.strftime("%d.%m.%Y")
                if policy_start_date
                else "—"
            )
        elif col == 5:
            return f"{payment_amount:,.2f} ₽" if payment_amount else "0 ₽"
        elif col == 6:
            return payment_date.strftime("%d.%m.%Y") if payment_date else "—"
        elif col == 7:
            return f"{income_amount:,.2f} ₽" if income_amount else "0 ₽"
        elif col == 8:
            return received_date.strftime("%d.%m.%Y") if received_date else "—"
        elif col == 9:
            return executor_name or "—"

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        if 0 <= section < len(self.headers):
            return self.headers[section]
        return super().headerData(section, orientation, role)


class IncomeTableView(BaseTableView):
    COLUMN_FIELD_MAP = {
        0: Policy.policy_number,
        1: Deal.description,
        2: Client.name,
        3: Policy.sales_channel,
        4: Policy.start_date,
        5: Payment.amount,
        6: Payment.payment_date,
        7: Income.amount,
        8: Income.received_date,
        9: Executor.full_name,
    }
    def __init__(
        self,
        parent=None,
        *,
        context: AppContext | None = None,
        deal_id=None,
        **kwargs,
    ):
        self._context = context
        self.deal_id = deal_id
        checkbox_map = {
            "Показывать выплаченные": self.load_data,
        }
        controller = IncomeTableController(self)
        super().__init__(
            parent=parent,
            model_class=Income,
            form_class=IncomeForm,
            entity_name="Доход",
            checkbox_map=checkbox_map,
            date_filter_field="received_date",
            controller=controller,
            **kwargs,
        )
        self.default_sort_column = 8
        self.default_sort_order = Qt.DescendingOrder
        self.current_sort_column = self.default_sort_column
        self.current_sort_order = self.default_sort_order

        # Разрешаем пользователю менять ширину столбцов
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        # разрешаем множественный выбор для массовых действий
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.table.horizontalHeader().sortIndicatorChanged.connect(
            self.on_sort_changed
        )
        self.row_double_clicked.connect(self.open_detail)
        self.delete_callback = self.delete_selected
        # ensure toolbar reset action uses our override
        for act in self.toolbar.actions():
            if act.text() == "Сбросить":
                try:
                    act.triggered.disconnect()
                except TypeError:
                    pass
                act.triggered.connect(self._on_reset_filters)
                break
        self.load_data()

    def load_data(self):
        filters = self.get_filters()
        column_filters = filters.get("column_filters", {})
        logger.debug("\U0001F4C3 column_filters=%s", column_filters)
        logger.debug("\U0001F4CA Фильтры доходов: %s", filters)

        order_field = self.COLUMN_FIELD_MAP.get(
            self.current_sort_column, Income.received_date
        )
        if order_field is None:
            order_field = Income.received_date
        order_dir = (
            "desc" if self.current_sort_order == Qt.DescendingOrder else "asc"
        )
        join_executor = order_field is Executor.full_name

        logger.debug(
            "Income filters=%s order=%s %s page=%d",
            filters,
            order_field,
            order_dir,
            self.page,
        )
        query = get_incomes_page(
            self.page,
            self.per_page,
            order_by=order_field,
            order_dir=order_dir,
            join_executor=join_executor,
            **filters,
        )
        items = list(
            prefetch(query, Payment, Policy, Client, Deal, DealExecutor, Executor)
        )
        logger.debug("Income result rows=%d", len(items))
        total = build_income_query(join_executor=join_executor, **filters).count()
        logger.debug("\U0001F4E6 Загружено доходов: %d", len(items))

        self.set_model_class_and_items(self.model_class, items, total_count=total)

    def refresh(self):
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
        self.save_table_settings()
        self.load_data()

    def _on_reset_filters(self):
        self.clear_filters()
        self.clear_column_filters()
        self.save_table_settings()
        self.on_filter_changed()

    def on_filter_changed(self, *args, **kwargs):
        self.page = 1
        self.paginator.set_summary("")
        self.load_data()

    def set_model_class_and_items(self, model_class, items, total_count=None):
        super().set_model_class_and_items(
            model_class, items, total_count=total_count
        )
        self.model = IncomeTableModel(items, model_class)
        self.proxy.setSourceModel(self.model)
        self.table.setModel(self.proxy)
        total_sum = sum(i.amount for i in items)
        summary = f"Сумма: {total_sum:.2f} ₽" if items else ""
        self.paginator.set_summary(summary)

    def get_selected(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self.model.get_item(self._source_row(idx))

    def get_selected_multiple(self):
        indexes = self.table.selectionModel().selectedRows()
        return [
            self.model.get_item(self._source_row(i)) for i in indexes
        ]

    def get_selected_deal(self):
        income = self.get_selected()
        if not income:
            return None
        payment = getattr(income, "payment", None)
        if not payment:
            return None
        policy = getattr(payment, "policy", None)
        if not policy:
            return None
        return getattr(policy, "deal", None)

    def add_new(self):
        form = self.form_class()
        if form.exec():
            self.refresh()

    def edit_selected(self, _=None):
        income = self.get_selected()
        if income:
            dlg = self.detail_view_class(income, parent=self)
            dlg.exec()
            self.refresh()

    def delete_selected(self):
        incomes = self.get_selected_multiple()
        if not incomes:
            return
        if len(incomes) == 1:
            message = f"Удалить доход {incomes[0].amount} ₽?"
        else:
            message = f"Удалить {len(incomes)} доход(ов)?"
        if confirm(message):
            try:
                if len(incomes) == 1:
                    mark_income_deleted(incomes[0].id)
                else:
                    ids = [inc.id for inc in incomes]
                    mark_incomes_deleted(ids)
                self.refresh()
            except Exception as e:
                show_error(str(e))

    def open_detail(self, _=None):
        income = self.get_selected()
        if income:
            dlg = self.detail_view_class(income)
            dlg.exec()

    def on_sort_changed(self, column: int, order: Qt.SortOrder):
        """Reload data after header sort change."""
        self.current_sort_column = column
        self.current_sort_order = order
        self.refresh()
