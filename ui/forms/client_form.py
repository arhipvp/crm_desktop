import logging

logger = logging.getLogger(__name__)
from database.models import Client
from services.client_service import add_client, update_client
from ui.base.base_edit_form import BaseEditForm


class ClientForm(BaseEditForm):
    def __init__(self, client=None, parent=None):
        super().__init__(instance=client, model_class=Client, entity_name="клиент", parent=parent)

    EXTRA_HIDDEN = {"drive_folder_path", "drive_folder_link"}



    def save_data(self):
        data = self.collect_data()
        logger.debug("📤 Client form save_data: %r", data)
        if self.instance:
            if all(getattr(self.instance, k) == v for k, v in data.items()):
                return self.instance
            return update_client(self.instance, **data)
        return add_client(**data)

    def validate_data(self, data: dict) -> bool:
        """Валидация данных перед сохранением."""
        return True  # при необходимости расширить

