from peewee import prefetch
from PySide6.QtCore import Qt

from database.models import Client, Income, Payment, Policy, Deal
from services.income_service import build_income_query, mark_income_deleted
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
            return f"{obj.amount:,.2f} ₽" if obj.amount else "0 ₽"
        elif col == 5:
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
        self.default_sort_column = 5
        self.default_sort_order = Qt.DescendingOrder
        self.current_sort_column = self.default_sort_column
        self.current_sort_order = self.default_sort_order

        self.table.horizontalHeader().sectionClicked.connect(self.on_sort_requested)
        self.row_double_clicked.connect(self.open_detail)
        self.load_data()

    def get_filters(self) -> dict:
        filters = {
            "search_text": self.filter_controls.get_search_text(),
            "show_deleted": self.filter_controls.is_checked("Показывать удалённые"),
            "only_unreceived": not self.filter_controls.is_checked(
                "Показывать выплаченные"
            ),
        }
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

        query = build_income_query(**filters)
        page_query = query.paginate(self.page, self.per_page)
        items = prefetch(page_query, Payment, Policy, Client, Deal)
        total = query.count()

        self.set_model_class_and_items(self.model_class, items, total_count=total)

    def set_model_class_and_items(self, model_class, items, total_count=None):
        self.model = IncomeTableModel(items, model_class)
        self.proxy_model.setSourceModel(self.model)
        self.table.setModel(self.proxy_model)
        try:
            self.table.sortByColumn(self.default_sort_column, self.default_sort_order)
            self.table.resizeColumnsToContents()
        except NotImplementedError:
            pass
        if total_count is not None:
            self.total_count = total_count
            self.paginator.update(self.total_count, self.page)

    def get_selected(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self.model.get_item(self._source_row(idx))

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
        income = self.get_selected()
        if income and confirm(f"Удалить доход {income.amount} ₽?"):
            try:
                mark_income_deleted(income.id)
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
