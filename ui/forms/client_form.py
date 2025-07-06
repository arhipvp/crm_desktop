import logging

logger = logging.getLogger(__name__)
from database.models import Client
from services.client_service import (
    add_client,
    update_client,
    find_similar_clients,
    DuplicatePhoneError,
)
from ui.base.base_edit_form import BaseEditForm
from ui.common.message_boxes import confirm, show_error


class ClientForm(BaseEditForm):
    def __init__(self, client=None, parent=None):
        super().__init__(
            instance=client, model_class=Client, entity_name="клиент", parent=parent
        )

    EXTRA_HIDDEN = {"drive_folder_path", "drive_folder_link"}

    def save(self):
        try:
            saved = self.save_data()
            if saved:
                self.saved_instance = saved
                self.accept()
        except DuplicatePhoneError as e:
            show_error(str(e))
        except Exception:
            logger.exception("❌ Ошибка при сохранении в %s", self.__class__.__name__)
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self, "Ошибка", f"Не удалось сохранить {self.entity_name}."
            )

    def save_data(self):
        data = self.collect_data()
        logger.debug("📤 Client form save_data: %r", data)
        if self.instance:
            if all(getattr(self.instance, k) == v for k, v in data.items()):
                return self.instance
            return update_client(self.instance, **data)
        similar = find_similar_clients(data.get("name", ""))
        if similar:
            names = ", ".join(c.name for c in similar[:3])
            if not confirm(
                f"Найдены похожие клиенты: {names}\nСоздать нового?",
                title="Возможный дубликат",
            ):
                return None
        return add_client(**data)

    def validate_data(self, data: dict) -> bool:
        """Валидация данных перед сохранением."""
        return True  # при необходимости расширить
