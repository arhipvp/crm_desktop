from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QMessageBox, QAbstractItemView, QHeaderView

from database.models import Task
from ui.base.base_table_model import BaseTableModel
from services.task_service import (
    build_task_query,
    get_tasks_page,
    queue_task,
    notify_task,
    update_task,
    mark_task_deleted,
)
from ui.common.message_boxes import confirm, show_error
from ui.base.base_table_view import BaseTableView
from ui.common.delegates import StatusDelegate
from ui.common.filter_controls import FilterControls
from ui.common.styled_widgets import styled_button
from ui.forms.task_form import TaskForm
from ui.views.task_detail_view import TaskDetailView


class TaskTableModel(BaseTableModel):
    VISIBLE_FIELDS = [
        Task.title,
        Task.due_date,
        Task.deal,
        Task.policy,
        Task.dispatch_state,
    ]

    def __init__(self, objects, model_class, parent=None):
        super().__init__(objects, model_class, parent)
        self.fields = self.VISIBLE_FIELDS
        self.headers = [f.name for f in self.fields]


class TaskTableView(BaseTableView):
    """Таблица задач + фильтры и действия отправки."""

    def __init__(
        self,
        parent=None,
        *,
        deal_id: int | None = None,
        autoload: bool = True,
    ) -> None:
        super().__init__(
            parent=parent,
            model_class=Task,
            form_class=TaskForm,
            detail_view_class=TaskDetailView,
        )
        self.sort_field = "due_date"
        self.sort_order = "asc"
        self.deal_id = deal_id
        self.table.setItemDelegate(StatusDelegate(self.table))
        self.table.verticalHeader().setVisible(False)  # убираем нумерацию строк
        self.table.horizontalHeader().sortIndicatorChanged.connect(
            self.on_sort_changed
        )
        # Кнопка «Редактировать» должна сразу открывать форму задачи

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
            export_callback=self.export_csv,
            search_placeholder="Поиск…",
            settings_name=self.settings_id,
        )
        self.left_layout.insertWidget(0, self.filter_controls)

        # ────────────────── Кнопка «Отправить» ──────────────────
        self.send_btn = styled_button(
            "Отправить",
            icon="📤",
            tooltip="Поставить выбранные задачи в очередь Telegram",
            shortcut="Ctrl+Shift+S",
        )
        idx_stretch = self.button_row.count() - 1
        self.button_row.insertWidget(idx_stretch, self.send_btn)
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self._send_selected_tasks)

        self.remind_btn = styled_button(
            "Напомнить",
            icon="🔔",
            tooltip="Напомнить исполнителю о задаче",
        )
        self.button_row.insertWidget(idx_stretch, self.remind_btn)
        self.remind_btn.setEnabled(False)
        self.remind_btn.clicked.connect(self._notify_selected_tasks)

        # разрешаем множественный выбор и массовое удаление
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.delete_callback = self.delete_selected

        sel = self.table.selectionModel()
        sel.selectionChanged.connect(self._update_actions_state)
        if autoload:
            self.load_data()

    def _update_actions_state(self, *_):
        has_sel = bool(self.table.selectionModel().selectedRows())
        self.edit_btn.setEnabled(has_sel)
        if hasattr(self, "send_btn"):
            self.send_btn.setEnabled(has_sel)
        if hasattr(self, "remind_btn"):
            self.remind_btn.setEnabled(has_sel)

    def _selected_tasks(self) -> list[Task]:
        if not self.model:
            return []
        sel = self.table.selectionModel()
        return [
            self.model.get_item(self._source_row(index))
            for index in sel.selectedRows()
            if index.isValid()
        ]

    def _send_selected_tasks(self):
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
                logger.debug("[queue_task] failed for %s: %s", t.id, exc)
        QMessageBox.information(
            self,
            "Telegram",
            f"В очередь помещено: {sent}\nОшибок: {skipped}",
        )
        self.refresh()

    def _notify_selected_tasks(self):
        tasks = self._selected_tasks()
        if not tasks:
            return
        for t in tasks:
            try:
                notify_task(t.id)
            except Exception as exc:
                logger.debug("[notify_task] failed for %s: %s", t.id, exc)
        QMessageBox.information(self, "Напоминание", "Запрос отправлен")
        self.refresh()

    def delete_selected(self):
        tasks = self._selected_tasks()
        if not tasks:
            return
        msg = (
            f"Удалить {len(tasks)} задач?"
            if len(tasks) > 1
            else f"Удалить задачу №{tasks[0].id}?"
        )
        if not confirm(msg):
            return
        errors = 0
        for t in tasks:
            try:
                mark_task_deleted(t.id)
            except Exception as exc:
                errors += 1
                logger.debug("[delete_task] failed for %s: %s", t.id, exc)
        if errors:
            show_error(f"Ошибок: {errors}")
        else:
            QMessageBox.information(
                self,
                "Задачи удалены",
                f"Удалено: {len(tasks)}",
            )
        self.refresh()

    def get_filters(self) -> dict:
        filters = super().get_filters()
        filters.update(
            {
                "include_deleted": self.filter_controls.is_checked("Показывать удалённые"),
                "include_done": self.filter_controls.is_checked("Показывать выполненные"),
            }
        )
        filters.pop("show_deleted", None)
        return filters

    def refresh(self):
        try:
            from services.sheets_service import sync_tasks_from_sheet

            sync_tasks_from_sheet()
        except Exception:
            logger.debug("Sheets sync failed", exc_info=True)

        self.load_data()

    def load_data(self) -> None:
        logger.debug("📥 Используется метод загрузки: get_tasks_page")

        f = self.get_filters()
        logger.debug(
            "📋 Сортировка задач: field=%s, order=%s", self.sort_field, self.sort_order
        )

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
                column_filters=f.get("column_filters"),
            )
            total = build_task_query(
                include_done=f["include_done"],
                include_deleted=f["include_deleted"],
                search_text=f["search_text"],
                deal_id=self.deal_id,
                column_filters=f.get("column_filters"),
            ).count()
        else:
            items = get_tasks_page(
                page=self.page,
                per_page=self.per_page,
                include_done=f["include_done"],
                include_deleted=f["include_deleted"],
                search_text=f["search_text"],
                sort_field=self.sort_field,
                sort_order=self.sort_order,
                column_filters=f.get("column_filters"),
            )
            total = build_task_query(**f).count()

        prev_texts = [
            self.column_filters.get_text(i)
            for i in range(len(self.column_filters._editors))
        ]

        items = list(items)
        self.model = TaskTableModel(items, Task)
        self.proxy_model.setSourceModel(self.model)
        self.table.setModel(self.proxy_model)

        try:
            self.table.sortByColumn(
                self.current_sort_column, self.current_sort_order
            )
            self.table.resizeColumnsToContents()
        except NotImplementedError:
            pass

        self.total_count = total
        self.paginator.update(self.total_count, self.page, self.per_page)
        self.data_loaded.emit(self.total_count)

        headers = [
            self.model.headerData(i, Qt.Horizontal)
            for i in range(self.model.columnCount())
        ]
        self.column_filters.set_headers(
            headers, prev_texts, self.COLUMN_FIELD_MAP
        )
        QTimer.singleShot(0, self.load_table_settings)

        # при смене модели selectionModel пересоздаётся и теряет подключение
        # к обработчику выбора, поэтому подключаем сигнал заново, чтобы
        # действия (в том числе «Напомнить») корректно активировались
        self.table.selectionModel().selectionChanged.connect(
            self._update_actions_state
        )

        # сортировка без повторной загрузки данных
        header = self.table.horizontalHeader()
        self.current_sort_column = self.get_column_index(self.sort_field)
        self.current_sort_order = (
            Qt.DescendingOrder if self.sort_order == "desc" else Qt.AscendingOrder
        )
        header.blockSignals(True)
        self.table.sortByColumn(self.current_sort_column, self.current_sort_order)
        header.blockSignals(False)

        # ───── ВАЖНО: переносим title в начало ─────
        if self.model:
            if Task.title in self.model.fields:
                self.model.fields.remove(Task.title)
                self.model.fields.insert(0, Task.title)

        self._update_actions_state()

        # Колонка с заголовком должна быть видимой
        # Скрываем первый столбец только если это ``id``
        if self.table.model() and self.table.model().columnCount() > 0:
            first_field = self.model.fields[0].name if self.model else None
            if first_field == "id":
                self.table.setColumnHidden(0, True)

        if self.model:
            idx_title = self.model.fields.index(Task.title)
            idx_deal = self.model.fields.index(Task.deal)
            idx_policy = self.model.fields.index(Task.policy)
            for row, task in enumerate(self.model.objects):
                title_txt = task.title or "—"
                deal_txt = (
                    f"{task.deal.client.name} — {task.deal.description}"
                    if task.deal_id and task.deal and task.deal.client
                    else "—"
                )
                policy_txt = (
                    f"#{task.policy.policy_number}"
                    if task.policy_id and task.policy
                    else "—"
                )

                self.model.setData(
                    self.model.index(row, idx_title), title_txt, role=Qt.DisplayRole
                )
                self.model.setData(
                    self.model.index(row, idx_deal), deal_txt, role=Qt.DisplayRole
                )
                self.model.setData(
                    self.model.index(row, idx_policy), policy_txt, role=Qt.DisplayRole
                )
        # восстановление индикатора сортировки без вызова сигнала
        col = self.get_column_index(self.sort_field)
        order = Qt.DescendingOrder if self.sort_order == "desc" else Qt.AscendingOrder
        header.blockSignals(True)
        header.setSortIndicator(col, order)
        header.blockSignals(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, header.count()):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.resizeColumnsToContents()

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

    def _on_edit(self):
        """Обработчик кнопки «Редактировать»."""
        self.edit_selected()

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

