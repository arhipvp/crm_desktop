from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QTableView

from database.models import Task
from services.task_service import (build_task_query, get_tasks_page,
                                   mark_task_deleted, queue_task)
from ui.base.base_table_view import BaseTableView
from ui.common.delegates import StatusDelegate
from ui.common.filter_controls import FilterControls
from ui.common.message_boxes import confirm, show_error
from ui.common.styled_widgets import styled_button
from ui.forms.task_form import TaskForm
from ui.views import task_detail_view


class TaskTableView(BaseTableView):
    """Таблица задач + фильтры + кнопка отправки в Telegram‑бот."""

    def __init__(self, parent=None, *, deal_id: int | None = None):
        super().__init__(
            parent=parent,
            model_class=Task,
            form_class=TaskForm,
            detail_view_class=task_detail_view,
        )
        self.sort_field = "due_date"
        self.sort_order = "asc"
        self.deal_id = deal_id 
        self.table.setItemDelegate(StatusDelegate(self.table))
        self.table.verticalHeader().setVisible(False)  # убираем нумерацию строк
        self.table.horizontalHeader().sectionClicked.connect(self.on_sort_requested)
        self.edit_btn.clicked.connect(self.edit_selected)



        # ────────────────── Панель фильтров ──────────────────
        self.left_layout.removeWidget(self.filter_controls)
        self.filter_controls.deleteLater()
        self.filter_controls = FilterControls(
            search_callback=self.on_filter_changed,
            checkbox_map={
                "Показывать удалённые": self.on_filter_changed,
                "Показывать выполненные": self.on_filter_changed,
            },
            on_filter=self.on_filter_changed,
            search_placeholder="Поиск…",
        )
        self.left_layout.insertWidget(0, self.filter_controls)

        # ────────────────── Кнопка «Отправить» ──────────────────
        self.send_btn = styled_button(
            "Отправить", icon="📤",
            tooltip="Поставить выбранные задачи в очередь Telegram",
            shortcut="Ctrl+Shift+S",
        )
        idx_stretch = self.button_row.count() - 1
        self.button_row.insertWidget(idx_stretch, self.send_btn)
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self._queue_selected_tasks_to_telegram)

        sel = self.table.selectionModel()
        sel.selectionChanged.connect(self._update_actions_state)
        self.load_data()


    def _update_actions_state(self, *_):
        has_sel = bool(self.table.selectionModel().selectedRows())
        self.edit_btn.setEnabled(has_sel)
        self.send_btn.setEnabled(has_sel)

    def _selected_tasks(self) -> list[Task]:
        if not self.model:
            return []
        sel = self.table.selectionModel()
        return [self.model.get_item(self._source_row(index))
                for index in sel.selectedRows() if index.isValid()]

    def _queue_selected_tasks_to_telegram(self):
        tasks = self._selected_tasks()
        if not tasks:
            return
        sent, skipped = 0, 0
        for t in tasks:
            try:
                queue_task(t.id)
                sent += 1
            except Exception as exc:
                skipped += 1
                print(f"[queue_task] failed for {t.id}: {exc}")
        QMessageBox.information(
            self, "Telegram",
            f"В очередь помещено: {sent}\nОшибок: {skipped}",
        )
        self.refresh()

    def get_filters(self) -> dict:
        return {
            "search_text": self.filter_controls.get_search_text(),
            "include_deleted": self.filter_controls.is_checked("Показывать удалённые"),
            "include_done": self.filter_controls.is_checked("Показывать выполненные"),
        }
    def refresh(self):
        self.load_data()

    def load_data(self) -> None:
        logger.debug("📥 Используется метод загрузки: get_tasks_page")
        
        #self.table.setModel(None)  # сброс до загрузки данных

        f = self.get_filters()
        logger.debug("📋 Сортировка задач: field=%s, order=%s", self.sort_field, self.sort_order)

        if self.deal_id:
            items = get_tasks_page(
                page=self.page,
                per_page=self.per_page,
                include_done=f["include_done"],
                include_deleted=f["include_deleted"],
                search_text=f["search_text"],
                sort_field=self.sort_field,
                sort_order=self.sort_order,
                deal_id=self.deal_id,
            )
            total = build_task_query(
                include_done=f["include_done"],
                include_deleted=f["include_deleted"],
                search_text=f["search_text"],
                deal_id=self.deal_id,
            ).count()

            #items = items.order_by(Task.due_date).paginate(self.page, self.per_page)






        else:
            items = get_tasks_page(
                page=self.page,
                per_page=self.per_page,
                include_done=f["include_done"],
                include_deleted=f["include_deleted"],
                search_text=f["search_text"],
                sort_field=self.sort_field,
                sort_order=self.sort_order,
            )
            total = build_task_query(**f).count()

        self.set_model_class_and_items(Task, list(items), total_count=total)
        self.table.sortByColumn(self.get_column_index(self.sort_field),
                        Qt.DescendingOrder if self.sort_order == "desc" else Qt.AscendingOrder)

        self.proxy_model.setSourceModel(self.model)
        #self.table.setModel(self.proxy_model)








        # DEBUG: поля модели
        logger.debug("TaskTableView fields: %s", [f.name for f in self.model.fields])


        # ───── ВАЖНО: переносим title в начало ─────
        if self.model:
            if Task.title in self.model.fields:
                self.model.fields.remove(Task.title)
                self.model.fields.insert(0, Task.title)

        self._update_actions_state()

        if self.table.model() and self.table.model().columnCount() > 0:
            self.table.setColumnHidden(0, True)

        if self.model:
            idx_title  = self.model.fields.index(Task.title)
            idx_deal   = self.model.fields.index(Task.deal)
            idx_policy = self.model.fields.index(Task.policy)
            for row, task in enumerate(self.model.objects):
                title_txt = task.title or "—"
                deal_txt = f"{task.deal.client.name} — {task.deal.description}" if task.deal_id and task.deal and task.deal.client else "—"
                policy_txt = f"#{task.policy.policy_number}" if task.policy_id and task.policy else "—"
                



                self.model.setData(self.model.index(row, idx_title), title_txt, role=Qt.DisplayRole)
                self.model.setData(self.model.index(row, idx_deal), deal_txt, role=Qt.DisplayRole)
                self.model.setData(self.model.index(row, idx_policy), policy_txt, role=Qt.DisplayRole)
        # восстановление сортировки после обновления модели
        col = self.get_column_index(self.sort_field)
        order = Qt.DescendingOrder if self.sort_order == "desc" else Qt.AscendingOrder
        self.table.horizontalHeader().setSortIndicator(col, order)

        

        self._update_actions_state()

    def get_selected(self):
        return self.get_selected_object()


    def add_new(self):
        form = TaskForm(parent=self)
        if form.exec():
            self.refresh()

    def edit_selected(self, _=None):
        task = self.get_selected()
        if task:
            form = TaskForm(task, parent=self)
            if form.exec():
                self.refresh()

    def open_detail(self, obj=None):
        if obj is None:
            obj = self.get_selected()
        if obj:
            form = TaskForm(obj, parent=self)
            if form.exec():
                self.refresh()

    def on_sort_changed(self, column: int, order: Qt.SortOrder):
        if not self.model or column >= len(self.model.fields):
            return
        self.sort_field = self.model.fields[column].name
        self.sort_order = "desc" if order == Qt.DescendingOrder else "asc"
        self.load_data()
        
    def on_sort_requested(self, column: int):
        if not self.model or column >= len(self.model.fields):
            return

        field_name = self.model.fields[column].name

        if self.sort_field == field_name:
            self.sort_order = "desc" if self.sort_order == "asc" else "asc"
        else:
            self.sort_field = field_name
            self.sort_order = "asc"

        self.refresh()
