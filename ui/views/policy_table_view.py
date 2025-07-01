from database.models import Policy
from services.policy_service import (
    build_policy_query,
    get_policies_page,
    mark_policy_deleted,
    mark_policy_renewed,
    mark_policies_renewed,
    mark_policies_deleted,
)
from PySide6.QtWidgets import QAbstractItemView
from ui.base.base_table_view import BaseTableView
from ui.common.message_boxes import confirm, show_error
from ui.forms.policy_form import PolicyForm
from ui.views.policy_detail_view import PolicyDetailView
from ui.common.styled_widgets import styled_button


class PolicyTableView(BaseTableView):
    def __init__(self, parent=None, deal_id=None, **kwargs):
        self.deal_id = deal_id
        checkbox_map = {
            "Показывать продленное": self.on_filter_changed,
            "Показать полисы без сделок": self.on_filter_changed,
        }
        super().__init__(
            parent=parent,
            model_class=Policy,
            form_class=PolicyForm,
            checkbox_map=checkbox_map,
            **kwargs,
        )
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().sectionClicked.connect(self.on_section_clicked)

        self.order_by = "start_date"
        self.order_dir = "asc"

        self.mark_renewed_btn = styled_button("Полис продлен (без привязки)")
        idx = self.button_row.count() - 1
        self.button_row.insertWidget(idx, self.mark_renewed_btn)
        self.mark_renewed_btn.clicked.connect(self._on_mark_renewed)

        self.make_deal_btn = styled_button("Сделать сделку из полиса")
        idx = self.button_row.count() - 1
        self.button_row.insertWidget(idx, self.make_deal_btn)
        self.make_deal_btn.clicked.connect(self._on_make_deal)

        self.load_data()

    def get_filters(self) -> dict:
        filters = {
            "search_text": self.filter_controls.get_search_text(),
            "show_deleted": self.filter_controls.is_checked("Показывать удалённые"),
            "include_renewed": self.filter_controls.is_checked("Показывать продленное"),
            "without_deal_only": self.filter_controls.is_checked("Показать полисы без сделок"),
        }
        if self.deal_id is not None:
            filters["deal_id"] = self.deal_id
        return filters

    def load_data(self):
        filters = self.get_filters()
        items = get_policies_page(
            self.page,
            self.per_page,
            order_by=self.order_by,
            order_dir=self.order_dir,
            **filters,
        )
        total = build_policy_query(**filters).count()
        self.set_model_class_and_items(Policy, list(items), total_count=total)

    def get_selected(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        return self.model.get_item(idx.row())

    def get_selected_multiple(self):
        indexes = self.table.selectionModel().selectedRows()
        return [
            self.model.get_item(self.proxy_model.mapToSource(i).row()) for i in indexes
        ]

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
        policies = self.get_selected_multiple()
        if not policies:
            return
        if len(policies) == 1:
            message = f"Удалить полис {policies[0].policy_number}?"
        else:
            message = f"Удалить {len(policies)} полис(ов)?"
        if confirm(message):
            try:
                if len(policies) == 1:
                    mark_policy_deleted(policies[0].id)
                else:
                    ids = [p.id for p in policies]
                    mark_policies_deleted(ids)
                self.refresh()
            except Exception as e:
                show_error(str(e))

    def _on_mark_renewed(self):
        policies = self.get_selected_multiple()
        if not policies:
            return
        try:
            if len(policies) == 1:
                mark_policy_renewed(policies[0].id)
            else:
                if not confirm(
                    f"Отметить {len(policies)} полис(ов) продлёнными?"
                ):
                    return
                ids = [p.id for p in policies]
                mark_policies_renewed(ids)
            self.refresh()
        except Exception as e:
            show_error(str(e))

    def _on_make_deal(self):
        policy = self.get_selected()
        if not policy:
            return
        try:
            from services.deal_service import add_deal_from_policy
            from ui.views.deal_detail_view import DealDetailView

            deal = add_deal_from_policy(policy)
            self.refresh()
            dlg = DealDetailView(deal, parent=self)
            dlg.exec()
        except Exception as e:
            show_error(str(e))

    def open_detail(self, _=None):
        policy = self.get_selected()
        if policy:
            dlg = PolicyDetailView(policy)
            dlg.exec()

    def on_section_clicked(self, logicalIndex):
        field = self.model.fields[logicalIndex].name
        if not hasattr(Policy, field):
            return
        order = self.table.horizontalHeader().sortIndicatorOrder()
        self.order_dir = "desc" if order == 1 else "asc"
        self.order_by = field
        self.page = 1
        self.load_data()
