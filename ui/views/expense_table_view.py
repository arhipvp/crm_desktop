from PySide6.QtCore import Qt

from database.models import Expense
from services.expense_service import (build_expense_query, get_expenses_page,
                                      mark_expense_deleted)
from ui.base.base_table_model import BaseTableModel
from ui.base.base_table_view import BaseTableView
from ui.common.message_boxes import confirm, show_error
from ui.forms.expense_form import ExpenseForm
from ui.views.expense_detail_view import ExpenseDetailView


class ExpenseTableModel(BaseTableModel):
    
    def __init__(self, objects, model_class, parent=None):
        super().__init__(objects, model_class, parent)
        
        self.fields = []  # отключаем автоколонки
        self.headers = ["Полис", "Тип расхода", "Контрагент", "Сумма", "Дата выплаты"]



    def columnCount(self, parent=None):
        return len(self.headers)


    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None

        obj = self.objects[index.row()]
        policy = getattr(obj, "policy", None)
        payment = getattr(obj, "payment", None)

        col = index.column()

        if col == 0:
            return policy.policy_number if policy else "—"
        elif col == 1:
            return obj.expense_type or "—"
        elif col == 2:
            return getattr(payment, "contractor", None) or getattr(policy, "contractor", "—") if policy else "—"
        elif col == 3:
            return f"{obj.amount:,.2f} ₽" if obj.amount else "0 ₽"
        elif col == 4:
            return obj.expense_date.strftime("%d.%m.%Y") if obj.expense_date else "—"




    
        
        

class ExpenseTableView(BaseTableView):
    def __init__(self, parent=None, deal_id=None):
        checkbox_map = {
            "Показывать выплаченные": self.load_data,
        }
        self.deal_id = deal_id
        super().__init__(parent=parent, checkbox_map=checkbox_map)
        self.model_class = Expense            # или Client, Policy и т.д.
        self.form_class = ExpenseForm        # соответствующая форма
        self.virtual_fields = ["policy_num", "deal_desc", "client_name", "contractor"]
        
        self.row_double_clicked.connect(self.open_detail)
        self.load_data()
        

    def get_filters(self) -> dict:
        filters = {
            "search_text": self.filter_controls.get_search_text(),
            "show_deleted": self.filter_controls.is_checked("Показывать удалённые"),
            "only_unpaid": not self.filter_controls.is_checked("Показывать выплаченные"),
        }
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
        expense = self.get_selected()
        if not expense:
            return
        if confirm(f"Удалить расход {expense.amount} ₽?"):
            try:
                mark_expense_deleted(expense.id)
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
            self.paginator.update(self.total_count, self.page)

    def get_base_query(self):
        if self.deal_id:
            return expense_service.get_for_deal(self.deal_id)
        return super().get_base_query()
