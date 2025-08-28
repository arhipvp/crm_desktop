from ui.base.base_edit_form import BaseEditForm
from database.models import Executor
from services.executor_service import add_executor, update_executor
from ui.common.message_boxes import show_error


class ExecutorForm(BaseEditForm):
    def __init__(self, executor=None, parent=None):
        super().__init__(instance=executor, model_class=Executor, entity_name="исполнителя", parent=parent)

    def save_data(self):
        data = self.collect_data()
        if self.instance:
            return update_executor(self.instance, **data)
        # Validate required fields for creation
        if not data.get("full_name") or data.get("tg_id") is None:
            show_error("Укажите ФИО и Telegram ID исполнителя")
            return None
        return add_executor(**data)
