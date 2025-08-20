from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView

from database.models import Expense, Income
from services.expense_service import (
    build_expense_query,
    get_expenses_page,
    mark_expense_deleted,
    mark_expenses_deleted,
)
from ui.base.base_table_model import BaseTableModel
from ui.base.base_table_view import BaseTableView
from ui.common.message_boxes import confirm, show_error
from ui.forms.expense_form import ExpenseForm
from ui.views.expense_detail_view import ExpenseDetailView


class ExpenseTableModel(BaseTableModel):
    def __init__(self, objects, model_class, parent=None):
        super().__init__(objects, model_class, parent)

        self.fields = []  # отключаем автоколонки
        self.headers = [
            'Полис',
            'Сделка',
            'Клиент',
            'Дата начала',
            'Тип расхода',
            'Сумма платежа',
            'Дата платежа',
            'Доход по платежу',
            'Сумма расхода',
            'Дата выплаты',
        ]

    def columnCount(self, parent=None):
        return len(self.headers)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        if 0 <= section < len(self.headers):
            return self.headers[section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None

        obj = self.objects[index.row()]
        policy = getattr(obj, "policy", None)
        payment = getattr(obj, "payment", None)
        if not policy and payment:
            policy = getattr(payment, "policy", None)
        deal = getattr(policy, "deal", None) if policy else None

        col = index.column()

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
            return obj.expense_type or "—"
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
            if payment:
                incomes = payment.incomes.where(Income.is_deleted == False)
                total = sum(inc.amount for inc in incomes)
                return f"{total:,.2f} ₽"
            return "0 ₽"
        elif col == 8:
            return f"{obj.amount:,.2f} ₽" if obj.amount else "0 ₽"
        elif col == 9:
            return (
                obj.expense_date.strftime("%d.%m.%Y")
                if obj.expense_date
                else "—"
            )


class ExpenseTableView(BaseTableView):
    def __init__(self, parent=None, deal_id=None):
        checkbox_map = {
            "Показывать выплаченные": self.load_data,
        }
        self.deal_id = deal_id
        super().__init__(parent=parent, checkbox_map=checkbox_map)
        self.model_class = Expense  # или Client, Policy и т.д.
        self.form_class = ExpenseForm  # соответствующая форма
        self.virtual_fields = ["policy_num", "deal_desc", "client_name", "contractor"]

        self.default_sort_column = 9
        self.default_sort_order = Qt.DescendingOrder
        self.current_sort_column = self.default_sort_column
        self.current_sort_order = self.default_sort_order

        self.row_double_clicked.connect(self.open_detail)

        # разрешаем множественный выбор для массовых действий
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.delete_callback = self.delete_selected

        self.load_data()

    def get_filters(self) -> dict:
        filters = super().get_filters()
        filters.update(
            {
                "include_paid": self.filter_controls.is_checked(
                    "Показывать выплаченные"
                )
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
                filters["expense_date_range"] = (from_date, to_date)

        return filters

    def load_data(self):
        # 1) читаем фильтры
        filters = self.get_filters()
        if self.deal_id:
            filters["deal_id"] = self.deal_id

        # 2) получаем страницу и общее количество
        items = get_expenses_page(self.page, self.per_page, **filters)
        total = build_expense_query(**filters).count()

        # 3) обновляем модель и пагинатор
        self.set_model_class_and_items(Expense, list(items), total_count=total)

    def get_selected(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self.model.get_item(idx.row())

    def get_selected_multiple(self):
        indexes = self.table.selectionModel().selectedRows()
        return [self.model.get_item(self._source_row(i)) for i in indexes]

    def add_new(self):
        form = ExpenseForm()
        if form.exec():
            self.refresh()

    def edit_selected(self, _=None):
        expense = self.get_selected()
        if expense:
            form = ExpenseForm(expense)
            if form.exec():
                self.refresh()

    def delete_selected(self):
        expenses = self.get_selected_multiple()
        if not expenses:
            return
        if len(expenses) == 1:
            message = f"Удалить расход {expenses[0].amount} ₽?"
        else:
            message = f"Удалить {len(expenses)} расход(ов)?"
        if confirm(message):
            try:
                if len(expenses) == 1:
                    mark_expense_deleted(expenses[0].id)
                else:
                    ids = [exp.id for exp in expenses]
                    mark_expenses_deleted(ids)
                self.refresh()
            except Exception as e:
                show_error(str(e))

    def open_detail(self, _=None):
        expense = self.get_selected()
        if expense:
            dlg = ExpenseDetailView(expense)
            dlg.exec()

    def set_model_class_and_items(self, model_class, items, total_count=None):
        self.model = ExpenseTableModel(items, model_class)
        self.proxy_model.setSourceModel(self.model)
        self.table.setModel(self.proxy_model)
        try:
            self.table.sortByColumn(self.default_sort_column, self.default_sort_order)
            self.table.resizeColumnsToContents()
        except NotImplementedError:
            pass
        if total_count is not None:
            self.total_count = total_count
            self.paginator.update(self.total_count, self.page, self.per_page)

    def get_base_query(self):
        if self.deal_id:
            return expense_service.get_for_deal(self.deal_id)
        return super().get_base_query()
