from datetime import date

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QAbstractItemView

from database.models import Client, Deal, Expense, Payment, Policy
from services import expense_service
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
            'Контрагент',
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
        if not index.isValid():
            return None

        obj = self.objects[index.row()]
        policy = getattr(obj, "policy", None)
        payment = getattr(obj, "payment", None)
        if not policy and payment:
            policy = getattr(payment, "policy", None)
        deal = getattr(policy, "deal", None) if policy else None

        if role == Qt.BackgroundRole:
            payment_date = getattr(payment, "payment_date", None)
            if (
                obj.expense_date is None
                and payment_date
                and payment_date < date.today()
            ):
                return QBrush(QColor("#ffcccc"))
            return None

        if role != Qt.DisplayRole:
            return None

        col = index.column()

        if col == 0:
            return policy.policy_number if policy else "—"
        elif col == 1:
            return deal.description if deal else "—"
        elif col == 2:
            return policy.client.name if policy and policy.client else "—"
        elif col == 3:
            return policy.contractor if policy and policy.contractor else "—"
        elif col == 4:
            return (
                policy.start_date.strftime("%d.%m.%Y")
                if policy and policy.start_date
                else "—"
            )
        elif col == 5:
            return obj.expense_type or "—"
        elif col == 6:
            return (
                f"{payment.amount:,.2f} ₽" if payment and payment.amount else "0 ₽"
            )
        elif col == 7:
            return (
                payment.payment_date.strftime("%d.%m.%Y")
                if payment and payment.payment_date
                else "—"
            )
        elif col == 8:
            total = getattr(obj, "income_total", 0) or 0
            return f"{total:,.2f} ₽"
        elif col == 9:
            return f"{obj.amount:,.2f} ₽" if obj.amount else "0 ₽"
        elif col == 10:
            return (
                obj.expense_date.strftime("%d.%m.%Y")
                if obj.expense_date
                else "—"
            )


class ExpenseTableView(BaseTableView):
    COLUMN_FIELD_MAP = {
        0: Policy.policy_number,
        1: Deal.description,
        2: Client.name,
        3: Policy.contractor,
        4: Policy.start_date,
        5: Expense.expense_type,
        6: Payment.amount,
        7: Payment.payment_date,
        8: expense_service.INCOME_TOTAL,
        9: Expense.amount,
        10: Expense.expense_date,
    }

    def __init__(self, parent=None, deal_id=None):
        checkbox_map = {
            "Показывать выплаченные": self.load_data,
        }
        self.deal_id = deal_id
        super().__init__(
            parent=parent,
            checkbox_map=checkbox_map,
            date_filter_field="expense_date",
        )
        self.controller.get_column_filters = self.get_column_filters
        # Перенеподключаем сигнал фильтрации колонок, чтобы работать напрямую
        self.column_filters.filter_changed.disconnect()
        self.column_filters.filter_changed.connect(self._on_column_filter_changed)
        self.model_class = Expense  # или Client, Policy и т.д.
        self.form_class = ExpenseForm  # соответствующая форма
        self.virtual_fields = ["policy_num", "deal_desc", "client_name", "contractor"]

        self.default_sort_column = 10
        self.default_sort_order = Qt.DescendingOrder
        self.current_sort_column = self.default_sort_column
        self.current_sort_order = self.default_sort_order
        self.order_by = Expense.expense_date
        self.order_dir = "desc"

        self.table.horizontalHeader().sortIndicatorChanged.connect(
            self.on_sort_changed
        )
        self.row_double_clicked.connect(self.open_detail)

        # разрешаем множественный выбор для массовых действий
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.delete_callback = self.delete_selected

        self.load_data()

    def get_column_filters(self) -> dict:
        """Собрать фильтры по столбцам в виде {Field: text}."""
        result: dict = {}
        for col, field in self.COLUMN_FIELD_MAP.items():
            if field is None:
                continue
            text = self.column_filters.get_text(col)
            if text:
                result[field] = text
        return result

    def load_data(self):
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
        date_range = filters.pop("expense_date", None)
        if date_range:
            filters["expense_date_range"] = date_range

        items = list(
            expense_service.get_expenses_page(
                self.page,
                self.per_page,
                order_by=self.order_by,
                order_dir=self.order_dir,
                **filters,
            )
        )
        total_sum = sum(e.amount for e in items)
        if items:
            self.paginator.set_summary(f"Сумма: {total_sum:.2f} ₽")
        else:
            self.paginator.set_summary("")
        total = expense_service.build_expense_query(
            order_by=self.order_by, order_dir=self.order_dir, **filters
        ).count()

        # 3) обновляем модель и пагинатор
        self.set_model_class_and_items(Expense, items, total_count=total)

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

    def _on_column_filter_changed(self, column: int, text: str):
        self.on_filter_changed()
        self.save_table_settings()

    def on_sort_changed(self, column: int, order: Qt.SortOrder):
        field = self.COLUMN_FIELD_MAP.get(column)
        if field is None:
            return
        self.current_sort_column = column
        self.current_sort_order = order
        self.order_by = field
        self.order_dir = "desc" if order == Qt.DescendingOrder else "asc"
        self.page = 1
        self.load_data()

    def on_filter_changed(self, *args, **kwargs):
        self.paginator.set_summary("")
        self.page = 1
        self.load_data()

    def get_selected(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self.model.get_item(self._source_row(idx))

    def get_selected_multiple(self):
        indexes = self.table.selectionModel().selectedRows()
        return [self.model.get_item(self._source_row(i)) for i in indexes]

    def get_selected_deal(self):
        expense = self.get_selected()
        if not expense:
            return None
        policy = getattr(expense, "policy", None)
        if not policy:
            payment = getattr(expense, "payment", None)
            if payment:
                policy = getattr(payment, "policy", None)
        if not policy:
            return None
        return getattr(policy, "deal", None)

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
                    expense_service.mark_expense_deleted(expenses[0].id)
                else:
                    ids = [exp.id for exp in expenses]
                    expense_service.mark_expenses_deleted(ids)
                self.refresh()
            except Exception as e:
                show_error(str(e))

    def open_detail(self, _=None):
        expense = self.get_selected()
        if expense:
            dlg = ExpenseDetailView(expense)
            dlg.exec()

    def set_model_class_and_items(self, model_class, items, total_count=None):
        prev_texts = [
            self.column_filters.get_text(i)
            for i in range(len(self.column_filters._editors))
        ]
        self.model = ExpenseTableModel(items, model_class)
        self.proxy_model.setSourceModel(self.model)
        self.table.setModel(self.proxy_model)
        try:
            self.table.horizontalHeader().setSortIndicator(
                self.current_sort_column, self.current_sort_order
            )
            self.table.resizeColumnsToContents()
        except NotImplementedError:
            pass
        if total_count is not None:
            self.total_count = total_count
            self.paginator.update(self.total_count, self.page, self.per_page)
        headers = [
            self.model.headerData(i, Qt.Horizontal)
            for i in range(self.model.columnCount())
        ]
        self.column_filters.set_headers(
            headers, prev_texts, self.COLUMN_FIELD_MAP
        )
        QTimer.singleShot(0, self.load_table_settings)

    def get_base_query(self):
        if self.deal_id:
            return expense_service.get_expenses_by_deal(self.deal_id)
        return super().get_base_query()
