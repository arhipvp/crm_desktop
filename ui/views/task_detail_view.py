from ui.base.base_detail_view import BaseDetailView
from database.models import Task

class TaskDetailView(BaseDetailView):
    def __init__(self, task: Task, parent=None):
        super().__init__(task, parent=parent)
