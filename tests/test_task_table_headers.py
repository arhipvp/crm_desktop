from PySide6.QtCore import Qt

from ui.views.task_table_view import TaskTableModel
from database.models import Task


def test_task_table_dispatch_state_header(qapp):
    model = TaskTableModel([], Task)
    index = next(i for i, f in enumerate(model.fields) if f.name == "dispatch_state")
    assert model.headerData(index, Qt.Horizontal) == "Статус отправки"
