from PySide6.QtWidgets import QMessageBox

from ui.base.base_detail_view import BaseDetailView
from ui.forms.task_form import TaskForm
from ui.common.message_boxes import confirm
from services.task_service import mark_task_deleted
from database.models import Task


class TaskDetailView(BaseDetailView):
    def __init__(self, task: Task, parent=None):
        super().__init__(task, parent=parent)

    def edit(self):
        form = TaskForm(self.instance, parent=self)
        if form.exec():
            # Обновляем данные, если пользователь сохранил изменения
            self.instance = Task.get_by_id(self.instance.id)
            self._refresh_info()

    def delete(self):
        if confirm(f"Удалить задачу №{self.instance.id}?"):
            try:
                mark_task_deleted(self.instance.id)
                QMessageBox.information(self, "Задача удалена", "Задача помечена как удалённая")
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", str(e))

    def _refresh_info(self):
        while self.info_layout.count():
            item = self.info_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.populate_info_tab()
