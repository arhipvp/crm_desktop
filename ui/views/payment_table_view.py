from datetime import date

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QAbstractItemView, QMenu

from database.models import Payment, Policy
from services.payment_service import (
    build_payment_query,
    get_payments_page,
    mark_payment_deleted,
    mark_payments_paid,
)
from services.folder_utils import copy_text_to_clipboard
from ui.base.base_table_model import BaseTableModel
from ui.base.base_table_view import BaseTableView
from ui.base.table_controller import TableController
from ui.common.message_boxes import confirm, show_error
from ui.common.ru_headers import RU_HEADERS
from ui.common.styled_widgets import styled_button
from ui.forms.payment_form import PaymentForm
from ui.views.payment_detail_view import PaymentDetailView


class PaymentTableController(TableController):
    def set_model_class_and_items(self, model_class, items, total_count=None):
        total_sum = sum(p.amount for p in items)
        overdue_sum = sum(
            p.amount
            for p in items
            if not p.actual_payment_date
            and p.payment_date
            and p.payment_date < date.today()
        )

        header = self.view.table.horizontalHeader()
        prev_texts = header.get_all_filters() if hasattr(header, "get_all_filters") else []

        self.view.model = PaymentTableModel(items, model_class)
        self.view.proxy_model.setSourceModel(self.view.model)
        self.view.table.setModel(self.view.proxy_model)

        try:
            self.view.table.sortByColumn(
                self.view.current_sort_column, self.view.current_sort_order
            )
            self.view.table.resizeColumnsToContents()
        except NotImplementedError:
            pass

        if total_count is not None:
            self.view.total_count = total_count
            self.view.paginator.update(
                self.view.total_count, self.view.page, self.view.per_page
            )
            self.view.data_loaded.emit(self.view.total_count)

        headers = [
            self.view.model.headerData(i, Qt.Horizontal)
            for i in range(self.view.model.columnCount())
        ]
        if hasattr(header, "set_headers"):
            header.set_headers(headers, prev_texts, self.view.COLUMN_FIELD_MAP)
        QTimer.singleShot(0, self.view.load_table_settings)

        self.view.paginator.set_summary(
            f"Сумма: {total_sum} ₽ (просрочено: {overdue_sum} ₽)"
        )


class PaymentTableView(BaseTableView):
    COLUMN_FIELD_MAP = {
        0: Policy.policy_number,
        1: Payment.amount,
        2: Payment.payment_date,
        3: Payment.actual_payment_date,
        4: None,
        5: None,
    }

    def __init__(self, parent=None, deal_id=None, **kwargs):
        self.deal_id = deal_id
        self.default_sort_column = 2
        self.current_sort_column = self.default_sort_column
        self.current_sort_order = Qt.AscendingOrder
        self.order_by = Payment.payment_date
        self.order_dir = "asc"

        checkbox_map = {
            "Показывать оплаченные": lambda state: self.load_data(),
            "Показывать удалённые": lambda state: self.load_data(),
        }

        controller = PaymentTableController(
            self,
            model_class=Payment,
            get_page_func=lambda page, per_page, **f: get_payments_page(
                page, per_page, order_by=self.order_by, order_dir=self.order_dir, **f
            ),
            get_total_func=lambda **f: build_payment_query(
                order_by=self.order_by, order_dir=self.order_dir, **f
            ).count(),
            filter_func=self._apply_filters,
        )

        super().__init__(
            parent=parent,
            form_class=PaymentForm,
            checkbox_map=checkbox_map,
            date_filter_field="payment_date",
            controller=controller,
            **kwargs,
        )

        # разрешаем множественный выбор для массовых действий
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.horizontalHeader().sortIndicatorChanged.connect(
            self.on_sort_changed
        )

        # кнопка массового подтверждения оплаты
        self.mark_paid_btn = styled_button(
            "Отметить оплаченным",
            icon="✅",
            tooltip="Пометить выбранные платежи",
        )
        self.mark_paid_btn.clicked.connect(self._on_mark_paid)
        self.button_row.insertWidget(self.button_row.count() - 1, self.mark_paid_btn)

        self.row_double_clicked.connect(self.open_detail)
        self.load_data()

    def _apply_filters(self, filters: dict) -> dict:
        filters.update(
            {
                "include_paid": self.filter_controls.is_checked("Показывать оплаченные"),
            }
        )
        if self.deal_id is not None:
            filters["deal_id"] = self.deal_id
        date_range = filters.pop("payment_date", None)
        if date_range:
            filters["payment_date_range"] = date_range
        return filters

    def on_sort_changed(self, column: int, order: Qt.SortOrder):
        self.current_sort_column = column
        self.current_sort_order = order

        field = self.COLUMN_FIELD_MAP.get(column)
        if field is None:
            return
        self.order_dir = "desc" if order == Qt.DescendingOrder else "asc"
        self.order_by = field
        self.page = 1
        self.load_data()

    def on_filter_changed(self, *args, **kwargs):
        self.paginator.set_summary("")
        super().on_filter_changed(*args, **kwargs)

    def get_selected(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self.model.get_item(self._source_row(idx))

    def get_selected_multiple(self):
        indexes = self.table.selectionModel().selectedRows()
        return [self.model.get_item(self._source_row(i)) for i in indexes]

    def get_selected_deal(self):
        payment = self.get_selected()
        if not payment:
            return None
        policy = getattr(payment, "policy", None)
        if not policy:
            return None
        return getattr(policy, "deal", None)

    def add_new(self):
        form = PaymentForm()
        if form.exec():
            self.refresh()

    def edit_selected(self, _=None):
        payment = self.get_selected()
        if payment:
            form = PaymentForm(payment)
            if form.exec():
                self.refresh()

    def delete_selected(self):
        payment = self.get_selected()
        if not payment:
            return
        if confirm(f"Удалить платёж на {payment.amount} ₽?"):
            try:
                mark_payment_deleted(payment.id)
                self.refresh()
            except Exception as e:
                show_error(str(e))

    def open_selected_policy(self):
        payment = self.get_selected()
        if not payment:
            return
        policy = getattr(payment, "policy", None)
        if not policy:
            return
        from ui.views.policy_detail_view import PolicyDetailView

        PolicyDetailView(policy, parent=self).exec()

    def _on_table_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        self.table.selectRow(index.row())
        menu = QMenu(self)
        act_open = menu.addAction("Открыть/редактировать")
        act_policy = menu.addAction("Открыть полис")
        act_delete = menu.addAction("Удалить")
        act_folder = menu.addAction("Открыть папку")
        text = str(index.data() or "")
        act_copy = menu.addAction("Копировать значение")
        act_deal = menu.addAction("Открыть сделку")
        act_open.triggered.connect(self._on_edit)
        act_policy.triggered.connect(self.open_selected_policy)
        act_delete.triggered.connect(self._on_delete)
        act_folder.triggered.connect(self.open_selected_folder)
        act_copy.triggered.connect(lambda: copy_text_to_clipboard(text, parent=self))
        act_deal.triggered.connect(self.open_selected_deal)
        payment = self.get_selected()
        act_policy.setEnabled(bool(getattr(payment, "policy", None)))
        act_deal.setEnabled(bool(self.get_selected_deal()))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_mark_paid(self):
        payments = self.get_selected_multiple()
        if not payments:
            return
        if confirm(f"Отметить {len(payments)} платеж(ей) оплаченными?"):
            try:
                ids = [p.id for p in payments]
                mark_payments_paid(ids)
                self.refresh()
            except Exception as e:
                show_error(str(e))

    def open_detail(self, payment: Payment):
        if self.use_inline_details:
            self.set_detail_widget(PaymentDetailView(payment, parent=self))
        else:
            dlg = PaymentDetailView(payment, parent=self)
            dlg.exec()


class PaymentTableModel(BaseTableModel):
    def __init__(self, objects: list, model_class, parent=None):
        super().__init__(objects, model_class, parent)
        self.virtual_fields = ["has_income", "has_expense"]
        self.headers += ["Доход", "Расход"]

    def columnCount(self, parent=None):
        return len(self.fields) + len(self.virtual_fields)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        obj = self.objects[index.row()]
        col = index.column()

        if role == Qt.BackgroundRole:
            if (
                obj.actual_payment_date is None
                and obj.payment_date
                and obj.payment_date < date.today()
            ):
                return QBrush(QColor("#ffcccc"))
            return None

        if role == Qt.ForegroundRole:
            if (
                obj.actual_payment_date is None
                and obj.payment_date
                and obj.payment_date < date.today()
            ):
                return QBrush(QColor("red"))
            return None

        # Виртуальные поля — после стандартных
        if col >= len(self.fields):
            v_field = self.virtual_fields[col - len(self.fields)]

            if role == Qt.DisplayRole:
                if v_field == "has_income":
                    return "✅" if getattr(obj, "income_count", 0) > 0 else "—"
                if v_field == "has_expense":
                    return "💸" if getattr(obj, "expense_count", 0) > 0 else "—"

            return None

        # Обычные поля — как в BaseTableModel
        return super().data(index, role)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None

        if section < len(self.fields):
            field = self.fields[section]
            return RU_HEADERS.get(field.name, field.name)
        return self.headers[section]
