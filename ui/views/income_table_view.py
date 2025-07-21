from peewee import prefetch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QAbstractItemView

from database.models import Client, Income, Payment, Policy, Deal
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


class IncomeTableModel(BaseTableModel):
    VIRTUAL_FIELDS = [
        "payment_info",
        "deal_desc",
        "client_name",
        "contractor",
        "amount",
        "received",
    ]

    def __init__(self, objects, model_class, parent=None):
        super().__init__(objects, model_class, parent)
        self.fields = []  # отключаем стандартные поля модели

        self.virtual_fields = self.VIRTUAL_FIELDS
        self.headers = [
            "Полис",
            "Сделка",
            "Клиент",
            "Дата начала",
            "Сумма платежа",
            "Дата платежа",
            "Сумма комиссии",
            "Дата получения",
        ]

    def columnCount(self, parent=None):
        return len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        obj = self.objects[index.row()]
        col = index.column()
        if role != Qt.DisplayRole:
            return None

        payment = getattr(obj, "payment", None)
        policy = getattr(payment, "policy", None) if payment else None
        deal = getattr(policy, "deal", None) if policy else None

        if col == 0:
            return policy.policy_number if policy else "—"
        elif col == 1:
            return deal.description if deal else "—"
        elif col == 2:
            return policy.client.name if policy and policy.client else "—"
        elif col == 3:
            return (
                policy.start_date.strftime("%d.%m.%Y")
                if policy and policy.start_date
                else "—"
            )
        elif col == 4:
            return (
                f"{payment.amount:,.2f} ₽" if payment and payment.amount else "0 ₽"
            )
        elif col == 5:
            return (
                payment.payment_date.strftime("%d.%m.%Y")
                if payment and payment.payment_date
                else "—"
            )
        elif col == 6:
            return f"{obj.amount:,.2f} ₽" if obj.amount else "0 ₽"
        elif col == 7:
            return (
                obj.received_date.strftime("%d.%m.%Y")
                if obj.received_date
                else "—"
            )

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
        3: Policy.start_date,
        4: Payment.amount,
        5: Payment.payment_date,
        6: Income.amount,
        7: Income.received_date,
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
        )
        self.deal_id = deal_id
        self.default_sort_column = 7
        self.default_sort_order = Qt.DescendingOrder
        self.current_sort_column = self.default_sort_column
        self.current_sort_order = self.default_sort_order

        # Разрешаем пользователю менять ширину столбцов
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        # разрешаем множественный выбор для массовых действий
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.table.horizontalHeader().sectionClicked.connect(self.on_sort_requested)
        self.row_double_clicked.connect(self.open_detail)
        self.delete_callback = self.delete_selected
        self.load_data()

    def get_filters(self) -> dict:
        filters = super().get_filters()
        filters.update(
            {
                "include_received": self.filter_controls.is_checked(
                    "Показывать выплаченные"
                ),
            }
        )
        if self.deal_id:
            filters["deal_id"] = self.deal_id

        date_from = getattr(self.filter_controls, "_date_from", None)
        date_to = getattr(self.filter_controls, "_date_to", None)
        if date_from and date_to:
            from_date = date_from.date_or_none()
            to_date = date_to.date_or_none()
            if from_date or to_date:
                filters["received_date_range"] = (from_date, to_date)
        return filters

    def load_data(self):
        filters = self.get_filters()  # используем метод подкласса

        order_field = self.COLUMN_FIELD_MAP.get(
            self.current_sort_column, Income.received_date
        )
        order_dir = (
            "desc" if self.current_sort_order == Qt.DescendingOrder else "asc"
        )

        query = get_incomes_page(
            self.page,
            self.per_page,
            order_by=order_field,
            order_dir=order_dir,
            **filters,
        )
        items = prefetch(query, Payment, Policy, Client, Deal)
        total = build_income_query(**filters).count()

        self.set_model_class_and_items(self.model_class, items, total_count=total)

    def set_model_class_and_items(self, model_class, items, total_count=None):
        """Устанавливает модель таблицы и применяет сохранённые настройки."""
        self.model = IncomeTableModel(items, model_class)
        self.proxy_model.setSourceModel(self.model)
        self.table.setModel(self.proxy_model)

        try:
            self.table.resizeColumnsToContents()
        except NotImplementedError:
            pass

        if total_count is not None:
            self.total_count = total_count
            self.paginator.update(self.total_count, self.page)
            self.data_loaded.emit(self.total_count)

        headers = [
            self.model.headerData(i, Qt.Horizontal)
            for i in range(self.model.columnCount())
        ]
        self.column_filters.set_headers(headers)
        self.load_table_settings()

        # Показать индикатор сортировки на текущем столбце
        self.table.horizontalHeader().setSortIndicator(
            self.current_sort_column, self.current_sort_order
        )

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

    def on_sort_requested(self, column):
        if column == self.current_sort_column:
            self.current_sort_order = (
                Qt.DescendingOrder
                if self.current_sort_order == Qt.AscendingOrder
                else Qt.AscendingOrder
            )
        else:
            self.current_sort_column = column
            self.current_sort_order = Qt.AscendingOrder
        self.refresh()
