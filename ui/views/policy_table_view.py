# ui/views/policy_table_view.py

from database.models import Policy
from services.policy_service import (
    build_policy_query,
    get_policies_page,
    mark_policy_deleted,
    mark_policy_renewed,
)
from ui.base.base_table_view import BaseTableView
from ui.common.message_boxes import confirm, show_error
from ui.forms.policy_form import PolicyForm
from ui.views.policy_detail_view import PolicyDetailView
from ui.common.styled_widgets import styled_button





class PolicyTableView(BaseTableView):
    def __init__(self, parent=None, deal_id=None, **kwargs):
        self.deal_id = deal_id
        checkbox_map = {"Показывать продленное": self.on_filter_changed}
        super().__init__(
            parent=parent,
            model_class=Policy,
            form_class=PolicyForm,
            checkbox_map=checkbox_map,
            **kwargs,
        )
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().sectionClicked.connect(self.on_section_clicked)
        #self.row_double_clicked.connect(self.open_detail)
        self.order_by = "start_date"
        self.order_dir = "asc"
        # кнопка «Полис продлен (без привязки)»
        self.mark_renewed_btn = styled_button("Полис продлен (без привязки)")
        idx = self.button_row.count() - 1
        self.button_row.insertWidget(idx, self.mark_renewed_btn)
        self.mark_renewed_btn.clicked.connect(self._on_mark_renewed)
        self.load_data()

    def get_filters(self) -> dict:
        filters = {
            "search_text": self.filter_controls.get_search_text(),
            "show_deleted": self.filter_controls.is_checked("Показывать удалённые"),
            "include_renewed": self.filter_controls.is_checked("Показывать продленное"),
        }
        if getattr(self, "deal_id", None) is not None:
            filters["deal_id"] = self.deal_id
        return filters

    
    
    
    


    def load_data(self):
        # 1) читаем фильтры
        filters = self.get_filters()

        # 2) получаем страницу и общее количество
        items = get_policies_page(
            self.page,
            self.per_page,
            order_by=self.order_by,
            order_dir=self.order_dir,
            **filters,
        )

        total = build_policy_query(**filters).count()

        # 3) обновляем модель и пагинатор
        self.set_model_class_and_items(Policy, list(items), total_count=total)

    def get_selected(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self.model.get_item(idx.row())


    def add_new(self):
        form = PolicyForm()
        if form.exec():
            self.refresh()

    def edit_selected(self, _=None):
        policy = self.get_selected()
        if policy:
            form = PolicyForm(policy)
            if form.exec():
                self.refresh()

    def delete_selected(self):
        policy = self.get_selected()
        if not policy:
            return
        if confirm(f"Удалить полис {policy.policy_number}?"):
            try:
                mark_policy_deleted(policy.id)
                self.refresh()
            except Exception as e:
                show_error(str(e))

    def _on_mark_renewed(self):
        policy = self.get_selected()
        if not policy:
            return
        try:
            mark_policy_renewed(policy.id)
            self.refresh()
        except Exception as e:
            show_error(str(e))

    def open_detail(self, _=None):
        policy = self.get_selected()
        if policy:
            dlg = PolicyDetailView(policy)
            dlg.exec()
    def on_section_clicked(self, logicalIndex):
        # Получаем имя поля по номеру колонки
        field = self.model.fields[logicalIndex].name  # или self.model._fields[logicalIndex]
        if not hasattr(Policy, field):
        # Например, если столбец виртуальный, сортировать не получится
            return
        # Определяем направление сортировки
        order = self.table.horizontalHeader().sortIndicatorOrder()
        order_dir = "desc" if order == 1 else "asc"
        self.order_by = field
        self.order_dir = order_dir
        self.page = 1  # сбрасываем страницу
        self.load_data()
