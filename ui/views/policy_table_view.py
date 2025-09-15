from database.models import Policy, Client, Deal
from services.policies import (
    build_policy_query,
    get_policies_page,
    mark_policy_deleted,
    mark_policy_renewed,
    mark_policies_renewed,
    mark_policies_deleted,
    attach_premium,
)
from PySide6.QtWidgets import QAbstractItemView, QMenu
from PySide6.QtCore import Qt, QDate
from services.folder_utils import copy_text_to_clipboard
from ui.base.base_table_view import BaseTableView
from ui.base.base_table_model import BaseTableModel
from ui.base.table_controller import TableController
from ui.common.message_boxes import confirm, show_error
from ui.common.search_dialog import SearchDialog
from ui.forms.policy_form import PolicyForm
from ui.views.policy_detail_view import PolicyDetailView
from ui.common.styled_widgets import styled_button


class PolicyTableView(BaseTableView):
    COLUMN_FIELD_MAP = {
        0: Client.name,
        1: Deal.description,
        2: Policy.policy_number,
        3: Policy.insurance_type,
        4: Policy.insurance_company,
        5: Policy.contractor,
        6: Policy.sales_channel,
        7: Policy.start_date,
        8: Policy.end_date,
        9: Policy.vehicle_brand,
        10: Policy.vehicle_model,
        11: Policy.vehicle_vin,
        12: Policy.note,
        13: None,  # drive_folder_link
        14: Policy.renewed_to,
        15: None,  # premium
    }

    def __init__(self, parent=None, deal_id=None, **kwargs):
        self.deal_id = deal_id
        checkbox_map = {
            "Показывать продленное": self.on_filter_changed,
            "Показывать только полисы без сделок": self.on_filter_changed,
        }

        self.order_by = "start_date"
        self.order_dir = "asc"

        def _get_page(page, per_page, **f):
            items = list(
                get_policies_page(
                    page,
                    per_page,
                    order_by=self.order_by,
                    order_dir=self.order_dir,
                    **f,
                )
            )
            attach_premium(items)
            return items

        controller = TableController(
            self,
            model_class=Policy,
            get_page_func=_get_page,
            get_total_func=lambda **f: build_policy_query(**f).count(),
            filter_func=self._apply_filters,
        )

        super().__init__(
            parent=parent,
            form_class=PolicyForm,
            checkbox_map=checkbox_map,
            controller=controller,
            **kwargs,
        )
        self.setAcceptDrops(True)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().sortIndicatorChanged.connect(
            self.on_sort_changed
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )

        self.row_double_clicked.connect(self.open_detail)

        self.mark_renewed_btn = styled_button("Полис продлен (без привязки)")
        idx = self.button_row.count() - 1
        self.button_row.insertWidget(idx, self.mark_renewed_btn)
        self.mark_renewed_btn.clicked.connect(self._on_mark_renewed)

        self.make_deal_btn = styled_button("Сделать сделку из полиса")
        idx = self.button_row.count() - 1
        self.button_row.insertWidget(idx, self.make_deal_btn)
        self.make_deal_btn.clicked.connect(self._on_make_deal)

        self.link_deal_btn = styled_button("Привязать к сделке")
        idx = self.button_row.count() - 1
        self.button_row.insertWidget(idx, self.link_deal_btn)
        self.link_deal_btn.clicked.connect(self._on_link_deal)

        self.ai_btn = styled_button("🤖 Загрузить через ИИ")
        idx = self.button_row.count() - 1
        self.button_row.insertWidget(idx, self.ai_btn)
        self.ai_btn.clicked.connect(self._on_ai_import)

        self.load_data()

    def _apply_filters(self, filters: dict) -> dict:
        filters.update(
            {
                "include_renewed": self.filter_controls.is_checked("Показывать продленное"),
                "without_deal_only": self.filter_controls.is_checked("Показывать только полисы без сделок"),
            }
        )
        if self.deal_id is not None:
            filters["deal_id"] = self.deal_id
        return filters

    def get_selected(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        # map index through proxy to account for sorting/filtering
        source_row = self.proxy_model.mapToSource(idx).row()
        return self.model.get_item(source_row)

    def get_selected_multiple(self):
        indexes = self.table.selectionModel().selectedRows()
        return [
            self.model.get_item(self.proxy_model.mapToSource(i).row()) for i in indexes
        ]

    def get_selected_deal(self):
        policy = self.get_selected()
        if not policy:
            return None
        return getattr(policy, "deal", None)

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
        policies = self.get_selected_multiple()
        if not policies:
            return
        try:
            from services.deal_service import get_all_deals
            from services.policies import update_policy
            from ui.views.deal_detail import DealDetailView
            from ui.forms.deal_form import DealForm
            from utils.name_utils import extract_surname

            question = (
                "Привязать полис к существующей сделке?"
                if len(policies) == 1
                else f"Привязать {len(policies)} полис(ов) к существующей сделке?"
            )
            if confirm(question):
                deals = list(get_all_deals())
                if not deals:
                    show_error("Нет доступных сделок")
                    return

                labels = [f"{d.client.name} - {d.description}" for d in deals]
                dlg = SearchDialog(labels, parent=self)
                surname = extract_surname(policies[0].client.name)
                if surname:
                    dlg.search.setText(surname)
                if dlg.exec() and dlg.selected_index:
                    idx = labels.index(dlg.selected_index)
                    deal = deals[idx]
                    for p in policies:
                        update_policy(p, deal_id=deal.id)
                    self.refresh()
                return

            first = policies[0]
            form = DealForm(parent=self)
            form.refresh_client_combo(first.client_id)

            if first.start_date:
                form.fields["start_date"].setDate(
                    QDate(
                        first.start_date.year,
                        first.start_date.month,
                        first.start_date.day,
                    )
                )

            parts: list[str] = []
            if first.insurance_type:
                parts.append(first.insurance_type)
            if first.vehicle_brand:
                brand = first.vehicle_brand
                if first.vehicle_model:
                    brand += f" {first.vehicle_model}"
                parts.append(brand)
            description = " ".join(parts).strip() or f"Из полиса {first.policy_number}"
            form.fields["description"].setText(description)

            policy_numbers = ", ".join(p.policy_number for p in policies if p.policy_number)
            calc_text = (
                "Автоматически сгенеррированая сделка из полиса "
                f"{policy_numbers}"
            )
            form.fields["calculations"].setText(calc_text)

            if form.exec():
                deal = getattr(form, "saved_instance", None)
                if deal:
                    for p in policies:
                        update_policy(p, deal_id=deal.id)
                    self.refresh()
                    dlg = DealDetailView(deal, parent=self)
                    dlg.exec()
        except Exception as e:
            show_error(str(e))

    def _on_link_deal(self):
        policies = self.get_selected_multiple()
        if not policies:
            return
        try:
            from services.deal_service import get_all_deals
            from services.policies import update_policy

            deals = list(get_all_deals())
            if not deals:
                show_error("Нет доступных сделок")
                return

            labels = [f"{d.client.name} - {d.description}" for d in deals]
            dlg = SearchDialog(labels, parent=self)
            if dlg.exec() and dlg.selected_index:
                idx = labels.index(dlg.selected_index)
                deal = deals[idx]
                for p in policies:
                    update_policy(p, deal_id=deal.id)
                self.refresh()
        except Exception as e:
            show_error(str(e))

    def _on_ai_import(self):
        """Import policies using AI from one or multiple files."""
        from ui.forms.ai_policy_text_dialog import AiPolicyTextDialog
        from ui.forms.ai_policy_files_dialog import AiPolicyFilesDialog

        dlg = AiPolicyFilesDialog(parent=self)
        if dlg.exec():
            self.refresh()
            return

        dlg = AiPolicyTextDialog(parent=self)
        if dlg.exec():
            self.refresh()

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
        act_policy.triggered.connect(self.open_detail)
        act_delete.triggered.connect(self._on_delete)
        act_folder.triggered.connect(self.open_selected_folder)
        act_copy.triggered.connect(
            lambda: copy_text_to_clipboard(text, parent=self)
        )
        act_deal.triggered.connect(self.open_selected_deal)
        act_deal.setEnabled(bool(self.get_selected_deal()))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def open_detail(self, _=None):
        policy = self.get_selected()
        if policy:
            dlg = PolicyDetailView(policy)
            dlg.exec()

    def set_model_class_and_items(self, model_class, items, total_count=None):
        super().set_model_class_and_items(
            model_class, items, total_count=total_count
        )

    def on_sort_changed(self, logicalIndex: int, order: Qt.SortOrder):
        field = self.model.fields[logicalIndex].name
        if not hasattr(Policy, field):
            return
        self.current_sort_column = logicalIndex
        self.current_sort_order = order
        self.order_dir = "desc" if order == Qt.DescendingOrder else "asc"
        self.order_by = field
        self.page = 1
        self.load_data()

    # --- Drag and drop support -------------------------------------------------

    def dragEnterEvent(self, event):  # noqa: D401 - Qt override
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._orig_style = self.styleSheet()
            self.setStyleSheet(
                self._orig_style + "; border: 2px dashed #4CAF50;"
                if self._orig_style
                else "border: 2px dashed #4CAF50;"
            )

    def dragLeaveEvent(self, event):  # noqa: D401 - Qt override
        if hasattr(self, "_orig_style"):
            self.setStyleSheet(self._orig_style)


class PolicyTableModel(BaseTableModel):
    def __init__(self, objects, model_class, parent=None):
        super().__init__(objects, model_class, parent)
        self.virtual_fields = ["premium"]
        self.headers.append("Страховая премия")

    def columnCount(self, parent=None):
        return len(self.fields) + len(self.virtual_fields)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        obj = self.objects[index.row()]
        col = index.column()

        if col >= len(self.fields):
            if role == Qt.DisplayRole:
                return self.format_money(getattr(obj, "_premium", 0))
            if role == Qt.UserRole:
                return getattr(obj, "_premium", 0)
            if role == Qt.TextAlignmentRole:
                return Qt.AlignRight | Qt.AlignVCenter
            return None

        return super().data(index, role)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None

        if section < len(self.fields):
            return super().headerData(section, orientation, role)
        return self.headers[-1]

    def flags(self, index):
        flags = super().flags(index)
        if not index.isValid():
            return flags
        if index.column() >= len(self.fields):
            return flags & ~Qt.ItemIsEditable
        field = self.fields[index.column()]
        if field.name != "policy_number":
            return flags & ~Qt.ItemIsEditable
        return flags

    def setData(self, index, value, role=Qt.EditRole):  # pragma: no cover - read only
        return False

    def dropEvent(self, event):  # noqa: D401 - Qt override
        urls = [u for u in event.mimeData().urls() if u.isLocalFile()]
        if urls:
            files = [u.toLocalFile() for u in urls]
            if len(files) == 1:
                from ui.forms.ai_policy_text_dialog import AiPolicyTextDialog

                dlg = AiPolicyTextDialog(parent=self, file_path=files[0])
                if dlg.exec():
                    self.refresh()
            else:
                from PySide6.QtWidgets import QMessageBox
                import os
                import json as _json
                from services.policies.ai_policy_service import process_policy_bundle_with_ai
                from ui.forms.import_policy_json_form import ImportPolicyJsonForm
                from ui.common.message_boxes import show_error

                try:
                    data, conv = process_policy_bundle_with_ai(files)
                except Exception as e:  # pragma: no cover - network errors
                    show_error(str(e))
                    return

                msg = QMessageBox(self)
                msg.setWindowTitle("Диалог с ИИ")
                msg.setText(
                    "Распознавание файлов завершено. Полный диалог см. в деталях."
                )
                msg.setDetailedText(conv)
                msg.exec()

                json_text = _json.dumps(data, ensure_ascii=False, indent=2)
                dlg = ImportPolicyJsonForm(parent=self, json_text=json_text)
                if dlg.exec():
                    policy = getattr(dlg, "imported_policy", None)
                    if policy and policy.drive_folder_link:
                        from services.folder_utils import move_file_to_folder

                        for src in files:
                            move_file_to_folder(src, policy.drive_folder_link)
                    self.refresh()
            event.acceptProposedAction()
        if hasattr(self, "_orig_style"):
            self.setStyleSheet(self._orig_style)
