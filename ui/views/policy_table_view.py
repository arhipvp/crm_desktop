from __future__ import annotations

from datetime import date

from dateutil.relativedelta import relativedelta
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QAbstractItemView, QMenu

from core.app_context import AppContext
from services.deal_service import get_all_deals, get_deal_by_id
from services.folder_utils import copy_text_to_clipboard
from services.policies import CandidateDeal, find_candidate_deals, get_policy_by_id, update_policy
from services.policies.policy_app_service import policy_app_service
from services.policies.policy_table_controller import PolicyTableController
from services.policies.dto import PolicyRowDTO
from ui.base.base_table_view import BaseTableView
from ui.common.message_boxes import confirm, show_error, show_info
from ui.common.search_dialog import SearchDialog
from ui.common.styled_widgets import styled_button
from ui.forms.policy_form import PolicyForm
from ui.views.policy_detail_view import PolicyDetailView


class PolicyTableView(BaseTableView):
    COLUMN_FIELD_MAP = {
        0: "client_name",
        1: "deal_description",
        2: "policy_number",
        3: "insurance_type",
        4: "insurance_company",
        5: "contractor",
        6: "sales_channel",
        7: "start_date",
        8: "end_date",
        9: "vehicle_brand",
        10: "vehicle_model",
        11: "vehicle_vin",
        12: "note",
        13: None,  # drive_folder_link
        14: "renewed_to",
        15: None,  # premium
    }

    def __init__(
        self,
        parent=None,
        *,
        context: AppContext | None = None,
        deal_id=None,
        controller: PolicyTableController | None = None,
        service=policy_app_service,
        **kwargs,
    ):
        self._context = context
        self.deal_id = deal_id
        service = service or policy_app_service
        checkbox_map = {
            "Показывать продленное": self.on_filter_changed,
            "Показывать только полисы без сделок": self.on_filter_changed,
        }
        controller = controller or PolicyTableController(
            self,
            service=service,
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
        self.table.horizontalHeader().sortIndicatorChanged.connect(self.on_sort_changed)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )

        self.row_double_clicked.connect(self.open_detail)

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
                "include_renewed": self.is_checked("Показывать продленное"),
                "without_deal_only": self.is_checked("Показывать только полисы без сделок"),
            }
        )
        if self.deal_id is not None:
            filters["deal_id"] = self.deal_id
        return filters

    def get_selected(self) -> PolicyRowDTO | None:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        source_row = self.proxy.mapToSource(idx).row()
        return self.model.get_item(source_row)

    def get_selected_multiple(self) -> list[PolicyRowDTO]:
        indexes = self.table.selectionModel().selectedRows()
        return [self.model.get_item(self.proxy.mapToSource(i).row()) for i in indexes]

    def get_selected_deal(self):
        policy = self.get_selected()
        if not policy:
            return None
        return policy.deal

    def add_new(self):
        form = PolicyForm()
        if form.exec():
            self.refresh()

    def edit_selected(self, _=None):
        policy = self.get_selected()
        if not policy:
            return
        instance = get_policy_by_id(policy.id)
        if instance is None:
            show_error("Полис не найден")
            return
        form = PolicyForm(instance)
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
        if not confirm(message):
            return
        try:
            deleted_ids = self.controller.delete_policies(policies)
        except Exception as exc:  # noqa: BLE001
            show_error(str(exc))
            return
        if not deleted_ids:
            show_info("Полисы уже помечены удалёнными")
            return
        if len(deleted_ids) < len(policies):
            show_info("Некоторые полисы уже были помечены удалёнными")
        self.refresh()

    def _load_policy_instances(self, policies: list[PolicyRowDTO]):
        mapping = {}
        missing: list[int] = []
        for dto in policies:
            policy = get_policy_by_id(dto.id)
            if policy is None:
                missing.append(dto.id)
                continue
            mapping[dto.id] = policy
        return mapping, missing

    def _on_make_deal(self):
        policies = self.get_selected_multiple()
        if not policies:
            return
        mapping, missing = self._load_policy_instances(policies)
        if missing:
            missing_str = ", ".join(map(str, missing))
            show_error(f"Не найдены полисы с id: {missing_str}")
            return
        policy_models = [mapping[dto.id] for dto in policies]
        try:
            from ui.views.deal_detail import DealDetailView
            from ui.forms.deal_form import DealForm

            first = policy_models[0]
            form = DealForm(parent=self)
            if "reminder_date" in form.fields:
                base_date = first.start_date or date.today()
                reminder_date = base_date + relativedelta(months=9)
                form.fields["reminder_date"].setDate(
                    QDate(reminder_date.year, reminder_date.month, reminder_date.day)
                )
            form.refresh_client_combo(first.client_id)

            if first.start_date:
                form.fields["start_date"].setDate(
                    QDate(first.start_date.year, first.start_date.month, first.start_date.day)
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

            policy_numbers = ", ".join(
                p.policy_number for p in policy_models if p.policy_number
            )
            calc_text = (
                "Автоматически сгенерированная сделка из полиса "
                f"{policy_numbers}"
            )
            form.fields["calculations"].setText(calc_text)

            status_widget = form.fields.get("status")
            if status_widget is not None and hasattr(status_widget, "setText"):
                status_widget.setText("Автоматически созданная сделка")

            if not form.exec():
                return

            deal = getattr(form, "saved_instance", None)
            if not deal:
                return

            for policy in policy_models:
                update_policy(policy, deal_id=deal.id)
            self.refresh()

            dlg = DealDetailView(deal, parent=self)
            dlg.exec()
        except Exception as e:  # noqa: BLE001
            show_error(str(e))

    def _on_link_deal(self):
        policies = self.get_selected_multiple()
        if not policies:
            return
        mapping, missing = self._load_policy_instances(policies)
        if missing:
            missing_str = ", ".join(map(str, missing))
            show_error(f"Не найдены полисы с id: {missing_str}")
            return
        policy_models = [mapping[dto.id] for dto in policies]
        try:
            deals = list(get_all_deals())
            if not deals:
                show_error("Нет доступных сделок")
                return

            deals_by_id = {deal.id: deal for deal in deals}

            aggregated_candidates: dict[int, dict] = {}
            strict_matches: dict[int, CandidateDeal] = {}
            auto_link_possible = True
            for policy in policy_models:
                policy_candidates = find_candidate_deals(policy, limit=5)
                strict_candidates = [
                    candidate
                    for candidate in policy_candidates
                    if getattr(candidate, "is_strict", False)
                ]
                if len(strict_candidates) == 1:
                    strict_candidate = strict_candidates[0]
                    deal_obj = strict_candidate.deal or deals_by_id.get(
                        strict_candidate.deal_id
                    )
                    if deal_obj is None:
                        auto_link_possible = False
                    else:
                        if strict_candidate.deal is None:
                            strict_candidate.deal = deal_obj
                        strict_matches[policy.id] = strict_candidate
                else:
                    auto_link_possible = False
                for candidate in policy_candidates:
                    deal = candidate.deal or deals_by_id.get(candidate.deal_id)
                    if deal is None:
                        continue
                    entry = aggregated_candidates.setdefault(
                        candidate.deal_id,
                        {
                            "deal": deal,
                            "score": 0.0,
                            "combined_reasons": [],
                            "policy_reasons": {},
                            "supported_policies": set(),
                        },
                    )
                    entry["score"] += float(candidate.score or 0.0)
                    entry["supported_policies"].add(policy.id)
                    policy_reasons = list(candidate.reasons or [])
                    entry["policy_reasons"][policy.id] = policy_reasons
                    for reason in policy_reasons:
                        if reason not in entry["combined_reasons"]:
                            entry["combined_reasons"].append(reason)

            if (
                auto_link_possible
                and strict_matches
                and len(strict_matches) == len(policy_models)
            ):
                unique_deal_ids = {candidate.deal_id for candidate in strict_matches.values()}
                if len(unique_deal_ids) == 1:
                    deal_id = unique_deal_ids.pop()
                    deal = deals_by_id.get(deal_id)
                    if deal is None and strict_matches:
                        deal = next(iter(strict_matches.values())).deal
                    if deal is not None:
                        for policy in policy_models:
                            update_policy(policy, deal_id=deal.id)
                        self.refresh()
                        deal_name = deal.description or f"ID {deal.id}"
                        show_info(
                            "Полисы автоматически привязаны к сделке "
                            f'"{deal_name}"'
                        )
                        return

            candidate_items = []
            selected_policies = list(policy_models)
            for deal_id, entry in aggregated_candidates.items():
                deal = entry["deal"]
                if deal is None:
                    continue
                client_name = getattr(deal.client, "name", "Без клиента")
                description = deal.description or ""
                missing_policies = [
                    policy
                    for policy in selected_policies
                    if policy.id not in entry["policy_reasons"]
                ]

                details: list[str] = []
                for policy in selected_policies:
                    policy_label = policy.policy_number or f"ID {policy.id}"
                    reasons = entry["policy_reasons"].get(policy.id)
                    if reasons:
                        detail = f"Полис {policy_label}: {', '.join(reasons)}"
                    else:
                        detail = f"Полис {policy_label}: ⚠️ нет совпадений"
                    details.append(detail)

                comment_parts: list[str] = []
                if entry["combined_reasons"]:
                    comment_parts.append("; ".join(entry["combined_reasons"]))
                if missing_policies:
                    missing_labels = ", ".join(
                        policy.policy_number or f"ID {policy.id}"
                        for policy in missing_policies
                    )
                    comment_parts.append(f"⚠️ Нет совпадений для: {missing_labels}")

                candidate_items.append(
                    {
                        "score": entry["score"],
                        "title": client_name,
                        "subtitle": description,
                        "comment": " | ".join(comment_parts),
                        "value": {
                            "type": "candidate",
                            "deal": deal,
                            "supported_policy_ids": list(entry["supported_policies"]),
                            "unsupported_policy_ids": [
                                policy.id for policy in missing_policies
                            ],
                        },
                        "details": details,
                    }
                )

            def _candidate_sort_key(item: dict):
                score = -float(item.get("score") or 0.0)
                value = item.get("value") or {}
                deal_obj = value.get("deal")
                deal_id = getattr(deal_obj, "id", 0) if deal_obj is not None else 0
                return (score, deal_id)

            candidate_items.sort(key=_candidate_sort_key)
            max_candidates = 5
            if len(candidate_items) > max_candidates:
                candidate_items = candidate_items[:max_candidates]

            used_ids = {
                getattr(item.get("value", {}).get("deal"), "id", None)
                for item in candidate_items
                if item.get("value", {}).get("deal") is not None
            }

            manual_items = []
            for deal in deals:
                if deal.id in used_ids:
                    continue
                client_name = getattr(deal.client, "name", "Без клиента")
                manual_items.append(
                    {
                        "score": None,
                        "title": client_name,
                        "subtitle": deal.description or "",
                        "comment": "",
                        "value": {"type": "manual", "deal": deal},
                        "details": [],
                    }
                )

            dialog_items = candidate_items + manual_items
            dlg = SearchDialog(
                dialog_items,
                parent=self,
                make_deal_callback=lambda: self._on_make_deal(),
            )
            if not dlg.exec():
                return
            selected = dlg.selected_index
            if not selected:
                return
            deal = None
            unsupported_policy_ids: list[int] = []
            value_type = None
            if isinstance(selected, dict):
                deal = selected.get("deal")
                unsupported_policy_ids = list(selected.get("unsupported_policy_ids") or [])
                value_type = selected.get("type")
            else:
                if isinstance(selected, str):
                    deal = next(
                        (
                            item["value"]["deal"]
                            for item in dialog_items
                            if selected
                            in {
                                item.get("title"),
                                f"{item.get('title', '')} — {item.get('subtitle', '')}".strip(" —"),
                            }
                        ),
                        None,
                    )
                elif hasattr(selected, "id"):
                    deal = selected
            if not deal:
                return

            unsupported_policies = [
                policy
                for policy in policy_models
                if policy.id in set(unsupported_policy_ids)
            ]
            if value_type == "candidate" and unsupported_policies:
                policy_labels = ", ".join(
                    policy.policy_number or f"ID {policy.id}"
                    for policy in unsupported_policies
                )
                message = (
                    "Сделка не подтверждена для полисов: "
                    f"{policy_labels}. Привязать все равно?"
                )
                if not confirm(message):
                    return

            for policy in policy_models:
                update_policy(policy, deal_id=deal.id)
            self.refresh()
        except Exception as e:  # noqa: BLE001
            show_error(str(e))

    def _on_ai_import(self):
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

        def _copy_value() -> None:
            try:
                copy_text_to_clipboard(text)
            except Exception as exc:  # noqa: BLE001
                show_error(str(exc))

        act_copy.triggered.connect(_copy_value)
        act_deal.triggered.connect(self.open_selected_deal)
        act_deal.setEnabled(bool(self.get_selected_deal()))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def open_detail(self, _=None):
        policy = self.get_selected()
        if not policy:
            return
        instance = get_policy_by_id(policy.id)
        if instance is None:
            show_error("Полис не найден")
            return
        dlg = PolicyDetailView(instance, parent=self)
        dlg.exec()

    def open_selected_deal(self):
        policy = self.get_selected()
        if not policy or not policy.deal_id:
            return
        deal = get_deal_by_id(policy.deal_id)
        if deal is None:
            show_error("Сделка не найдена")
            return
        from ui.views.deal_detail import DealDetailView

        DealDetailView(deal, parent=self).exec()

    def on_sort_changed(self, logical_index: int, order: Qt.SortOrder):
        field = self.COLUMN_FIELD_MAP.get(logical_index)
        if field is None:
            return
        self.current_sort_column = logical_index
        self.current_sort_order = order
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

    def dropEvent(self, event):  # noqa: D401 - Qt override
        urls = [u for u in event.mimeData().urls() if u.isLocalFile()]
        if not urls:
            return
        files = [u.toLocalFile() for u in urls]
        try:
            if len(files) == 1:
                from ui.forms.ai_policy_text_dialog import AiPolicyTextDialog

                dlg = AiPolicyTextDialog(parent=self, file_path=files[0])
                if dlg.exec():
                    self.refresh()
            else:
                from PySide6.QtWidgets import QMessageBox
                import json as _json
                from services.policies.ai_policy_service import process_policy_bundle_with_ai
                from ui.forms.import_policy_json_form import ImportPolicyJsonForm

                data, conv = process_policy_bundle_with_ai(files)

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
        except Exception as exc:  # noqa: BLE001
            show_error(str(exc))
        finally:
            if hasattr(self, "_orig_style"):
                self.setStyleSheet(self._orig_style)
