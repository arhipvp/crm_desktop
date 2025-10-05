import logging
from datetime import date, datetime

from typing import Any

from peewee import Field
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QAbstractItemView

from core.app_context import AppContext

from database.models import Client, Deal, Expense, Payment, Policy
from services import expense_service
from ui.base.base_table_model import BaseTableModel
from ui.base.base_table_view import BaseTableView
from ui.base.table_controller import TableController
from ui.common.colors import HIGHLIGHT_COLOR_INCOME
from ui.common.message_boxes import confirm, show_error
from ui.forms.expense_form import ExpenseForm
from ui.views.expense_detail_view import ExpenseDetailView


logger = logging.getLogger(__name__)


class ExpenseTableController(TableController):
    def __init__(self, view) -> None:
        super().__init__(view, model_class=Expense)

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
        include_paid = bool(filters.get("include_paid", True))
        deal_id = filters.get("deal_id")
        expense_date_range = filters.get("expense_date_range")

        query = expense_service.build_expense_query(
            search_text=search_text,
            show_deleted=show_deleted,
            deal_id=deal_id,
            include_paid=include_paid,
            expense_date_range=expense_date_range,
            column_filters=column_filters,
        )

        if isinstance(column_field, Field):
            target_field = column_field
        else:
            mapping: dict[str, Field] = {
                "expense_type": Expense.expense_type,
                "amount": Expense.amount,
                "expense_date": Expense.expense_date,
            }
            target_field = mapping.get(column_key)

        if target_field is None:
            return []

        values_query = (
            query.select(target_field)
            .where(target_field.is_null(False))
            .distinct()
            .order_by(target_field.asc())
        )

        return [
            {"value": value, "display": value}
            for (value,) in values_query.tuples()
        ]


class ExpenseTableModel(BaseTableModel):
    def __init__(self, objects, model_class, parent=None):
        super().__init__(objects, model_class, parent)

        self.fields = []  # отключаем автоколонки
        self.headers = [
            "Полис",
            "Сделка",
            "Клиент",
            "Контрагент",
            "Дата начала",
            "Тип расхода",
            "Сумма платежа",
            "Дата платежа",
            "Доход по платежу",
            "Прочие расходы",
            "Чистый доход",
            "Сумма расхода",
            "Дата выплаты",
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
        def to_qdate(value):
            if isinstance(value, QDate):
                return value
            if isinstance(value, datetime):
                value = value.date()
            if isinstance(value, date):
                return QDate(value.year, value.month, value.day)
            return None

        policy = getattr(obj, "policy", None)
        payment = getattr(obj, "payment", None)
        if not policy and payment:
            policy = getattr(payment, "policy", None)
        deal = getattr(policy, "deal", None) if policy else None

        if role == Qt.BackgroundRole:
            if getattr(obj, "income_total", 0) > 0:
                return QBrush(QColor(HIGHLIGHT_COLOR_INCOME))
            return None

        if role == Qt.ToolTipRole and index.column() == 9:
            if payment:
                details = getattr(obj, "other_expense_details", None)
                if details is None:
                    others = expense_service.get_other_expenses(payment.id, obj.id)
                    details = "\n".join(
                        f"{e.expense_type or '—'} — {self.format_money(e.amount)} — "
                        f"{e.expense_date.strftime('%d.%m.%Y') if e.expense_date else '—'}"
                        for e in others
                    )
                    obj.other_expense_details = details
                return details or None
            return None
        col = index.column()

        policy_number = policy.policy_number if policy else None
        deal_description = deal.description if deal else None
        client_name = policy.client.name if policy and policy.client else None
        contractor = policy.contractor if policy and policy.contractor else None
        policy_start_date = policy.start_date if policy and policy.start_date else None
        policy_start_qdate = to_qdate(policy_start_date)
        expense_type = obj.expense_type or None
        payment_amount = payment.amount if payment else None
        payment_date = payment.payment_date if payment and payment.payment_date else None
        payment_qdate = to_qdate(payment_date)
        income_total = getattr(obj, "income_total", None)
        other_total = getattr(obj, "other_expense_total", None)
        net_income = getattr(obj, "net_income", None)
        expense_amount = obj.amount if obj.amount is not None else None
        expense_date = obj.expense_date
        expense_qdate = to_qdate(expense_date)

        raw_values = {
            0: policy_number,
            1: deal_description,
            2: client_name,
            3: contractor,
            4: policy_start_qdate,
            5: expense_type,
            6: payment_amount,
            7: payment_qdate,
            8: income_total,
            9: other_total,
            10: net_income,
            11: expense_amount,
            12: expense_qdate,
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
            return contractor or "—"
        elif col == 4:
            return (
                policy_start_date.strftime("%d.%m.%Y")
                if policy_start_date
                else "—"
            )
        elif col == 5:
            return expense_type or "—"
        elif col == 6:
            return (
                self.format_money(payment_amount)
                if payment_amount
                else "0 ₽"
            )
        elif col == 7:
            return payment_date.strftime("%d.%m.%Y") if payment_date else "—"
        elif col == 8:
            return (
                self.format_money(income_total)
                if income_total
                else "0 ₽"
            )
        elif col == 9:
            return (
                self.format_money(other_total)
                if other_total
                else "0 ₽"
            )
        elif col == 10:
            return (
                self.format_money(net_income)
                if net_income
                else "0 ₽"
            )
        elif col == 11:
            return self.format_money(expense_amount) if expense_amount else "0 ₽"
        elif col == 12:
            return expense_date.strftime("%d.%m.%Y") if expense_date else "—"


class ExpenseTableView(BaseTableView):
    COLUMN_FIELD_MAP = {
        0: Policy.policy_number,
        1: Deal.description,
        2: Client.name,
        3: Policy.contractor,
        4: Policy.start_date,
        5: "expense_type",
        6: Payment.amount,
        7: Payment.payment_date,
        8: expense_service.INCOME_TOTAL,
        9: expense_service.OTHER_EXPENSE_TOTAL,
        10: expense_service.NET_INCOME,
        11: "amount",
        12: "expense_date",
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
        checkbox_map = {
            "Показывать выплаченные": self.load_data,
        }
        self.deal_id = deal_id
        controller = ExpenseTableController(self)
        super().__init__(
            parent=parent,
            checkbox_map=checkbox_map,
            date_filter_field="expense_date",
            controller=controller,
            **kwargs,
        )
        self.model_class = Expense  # или Client, Policy и т.д.
        self.form_class = ExpenseForm  # соответствующая форма
        self.virtual_fields = ["policy_num", "deal_desc", "client_name", "contractor"]

        self.default_sort_column = 12
        self.default_sort_order = Qt.DescendingOrder
        self.current_sort_column = self.default_sort_column
        self.current_sort_order = self.default_sort_order
        self.order_by = Expense.expense_date
        self.order_dir = "desc"

        self.table.horizontalHeader().sortIndicatorChanged.connect(self.on_sort_changed)
        self.row_double_clicked.connect(self.open_detail)

        # разрешаем множественный выбор для массовых действий
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.delete_callback = self.delete_selected

        self.load_data()

    def load_data(self):
        filters = super().get_filters()
        filters.update(
            {"include_paid": self.is_checked("Показывать выплаченные")}
        )
        if self.deal_id:
            filters["deal_id"] = self.deal_id
        date_range = filters.pop("expense_date", None)
        if date_range:
            filters["expense_date_range"] = date_range

        logger.debug(
            "Expense filters=%s order=%s %s page=%d",
            filters,
            self.order_by,
            self.order_dir,
            self.page,
        )
        items = list(
            expense_service.get_expenses_page(
                self.page,
                self.per_page,
                order_by=self.order_by,
                order_dir=self.order_dir,
                **filters,
            )
        )
        logger.debug("Expense result rows=%d", len(items))
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
        super().set_model_class_and_items(
            model_class, items, total_count=total_count
        )
        # Используем специализированную модель для отображения человекочитаемых колонок
        self.model = ExpenseTableModel(items, model_class)
        self.proxy.setSourceModel(self.model)
        self.table.setModel(self.proxy)
        total_sum = sum(e.amount for e in items)
        summary = f"Сумма: {total_sum:.2f} ₽" if items else ""
        self.paginator.set_summary(summary)

    def get_base_query(self):
        if self.deal_id:
            return expense_service.get_expenses_by_deal(self.deal_id)
        return super().get_base_query()
