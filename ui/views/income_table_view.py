import logging
from peewee import prefetch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QAbstractItemView

from database.models import Client, Income, Payment, Policy, Deal, Executor, DealExecutor
from services.income_service import (
    build_income_query,
    mark_income_deleted,
    mark_incomes_deleted,
    get_incomes_page,
)
from ui.base.base_table_model import BaseTableModel
from ui.base.base_table_view import BaseTableView
from ui.common.message_boxes import confirm, show_error
from ui.forms.income_form import IncomeForm


logger = logging.getLogger(__name__)


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

        payment = getattr(obj, "payment", None)
        policy = getattr(payment, "policy", None) if payment else None
        deal = getattr(policy, "deal", None) if policy else None

        if role != Qt.DisplayRole:
            return None

        if col == 0:
            return policy.policy_number if policy else "—"
        elif col == 1:
            return deal.description if deal else "—"
        elif col == 2:
            return policy.client.name if policy and policy.client else "—"
        elif col == 3:
            return policy.sales_channel if policy and policy.sales_channel else "—"
        elif col == 4:
            return (
                policy.start_date.strftime("%d.%m.%Y")
                if policy and policy.start_date
                else "—"
            )
        elif col == 5:
            return (
                f"{payment.amount:,.2f} ₽" if payment and payment.amount else "0 ₽"
            )
        elif col == 6:
            return (
                payment.payment_date.strftime("%d.%m.%Y")
                if payment and payment.payment_date
                else "—"
            )
        elif col == 7:
            return f"{obj.amount:,.2f} ₽" if obj.amount else "0 ₽"
        elif col == 8:
            return (
                obj.received_date.strftime("%d.%m.%Y")
                if obj.received_date
                else "—"
            )
        elif col == 9:
            if deal and getattr(deal, "executors", None):
                ex = deal.executors[0].executor
                return ex.full_name if ex else "—"
            return "—"

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
    def __init__(self, parent=None, deal_id=None):
        checkbox_map = {
            "Показывать выплаченные": self.load_data,
        }
        super().__init__(
            parent=parent,
            model_class=Income,
            form_class=IncomeForm,
            entity_name="Доход",
            checkbox_map=checkbox_map,
            date_filter_field="received_date",
        )
        self.deal_id = deal_id
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
        self.load_data()

    def get_filters(self) -> dict:
        filters = super().get_filters()
        filters.update(
            {
                "include_received": self.filter_controls.is_checked(
                    "Показывать выплаченные"
                )
            }
        )
        if self.deal_id:
            filters["deal_id"] = self.deal_id
        date_range = filters.pop("received_date", None)
        if date_range:
            filters["received_date_range"] = date_range
        logger.debug("\U0001F4C3 column_filters=%s", filters.get("column_filters"))
        return filters

    def load_data(self):
        filters = self.get_filters()  # используем метод подкласса
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
        total = build_income_query(join_executor=join_executor, **filters).count()
        logger.debug("\U0001F4E6 Загружено доходов: %d", len(items))

        self.set_model_class_and_items(self.model_class, items, total_count=total)

    def refresh(self):
        self.load_data()

    def on_filter_changed(self, *args, **kwargs):
        self.page = 1
        self.paginator.set_summary("")
        self.load_data()

    def set_model_class_and_items(self, model_class, items, total_count=None):
        super().set_model_class_and_items(
            model_class, items, total_count=total_count
        )
        total_sum = sum(i.amount for i in items)
        summary = f"Сумма: {total_sum:.2f} ₽" if items else ""
        self.paginator.set_summary(summary)

        # В интерактивном режиме пользователь сам выбирает ширину
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)

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
