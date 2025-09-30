import logging

from PySide6.QtWidgets import QCheckBox, QLineEdit, QPlainTextEdit

from services.clients.client_app_service import (
    DuplicatePhoneError,
    client_app_service,
)
from services.clients.dto import (
    ClientCreateCommand,
    ClientDetailsDTO,
    ClientUpdateCommand,
)
from ui.base.base_edit_form import BaseEditForm
from ui.common.message_boxes import confirm, show_error


logger = logging.getLogger(__name__)


class ClientForm(BaseEditForm):
    """Форма создания и редактирования клиента, работающая через DTO."""

    def __init__(self, client: ClientDetailsDTO | None = None, parent=None):
        self._service = client_app_service
        self.name_edit: QLineEdit | None = None
        self.phone_edit: QLineEdit | None = None
        self.email_edit: QLineEdit | None = None
        self.company_checkbox: QCheckBox | None = None
        self.note_edit: QPlainTextEdit | None = None
        super().__init__(
            instance=client,
            model_class=ClientDetailsDTO,
            entity_name="клиент",
            parent=parent,
        )

    def build_form(self):  # type: ignore[override]
        self.name_edit = QLineEdit()
        self.phone_edit = QLineEdit()
        self.email_edit = QLineEdit()
        self.company_checkbox = QCheckBox("Компания")
        self.note_edit = QPlainTextEdit()

        self.fields = {
            "name": self.name_edit,
            "phone": self.phone_edit,
            "email": self.email_edit,
            "is_company": self.company_checkbox,
            "note": self.note_edit,
        }

        self.form_layout.addRow("Имя", self.name_edit)
        self.form_layout.addRow("Телефон", self.phone_edit)
        self.form_layout.addRow("Email", self.email_edit)
        self.form_layout.addRow("Статус", self.company_checkbox)
        self.form_layout.addRow("Заметки", self.note_edit)

        self.name_edit.textChanged.connect(self._mark_dirty)
        self.phone_edit.textChanged.connect(self._mark_dirty)
        self.email_edit.textChanged.connect(self._mark_dirty)
        self.company_checkbox.stateChanged.connect(self._mark_dirty)
        self.note_edit.textChanged.connect(self._mark_dirty)

        if self.instance:
            self.fill_from_obj(self.instance)

    def fill_from_obj(self, obj):  # type: ignore[override]
        if not isinstance(obj, ClientDetailsDTO):
            return
        self.name_edit.setText(obj.name or "")
        self.phone_edit.setText(obj.phone or "")
        self.email_edit.setText(obj.email or "")
        self.company_checkbox.setChecked(bool(obj.is_company))
        self.note_edit.setPlainText(obj.note or "")

    def collect_data(self) -> dict:  # type: ignore[override]
        name = self.name_edit.text().strip() if self.name_edit else ""
        phone = self.phone_edit.text().strip() if self.phone_edit else ""
        email = self.email_edit.text().strip() if self.email_edit else ""
        note = self.note_edit.toPlainText().strip() if self.note_edit else ""
        is_company = self.company_checkbox.isChecked() if self.company_checkbox else False
        return {
            "name": name,
            "phone": phone or None,
            "email": email or None,
            "is_company": is_company,
            "note": note or None,
        }

    def validate_data(self, data: dict) -> bool:  # type: ignore[override]
        if not data.get("name"):
            show_error("Имя обязательно")
            return False
        return True

    def save(self):  # type: ignore[override]
        try:
            saved = self.save_data()
            if saved:
                self.saved_instance = saved
                self.accept()
        except DuplicatePhoneError as exc:
            show_error(str(exc))
        except Exception:
            logger.exception("❌ Ошибка при сохранении в %s", self.__class__.__name__)
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self, "Ошибка", f"Не удалось сохранить {self.entity_name}."
            )

    def save_data(self):  # type: ignore[override]
        data = self.collect_data()
        logger.debug("📤 Сохранение формы клиента: %r", data)

        if not self.validate_data(data):
            return None

        if self.instance:
            if self._is_unchanged(data):
                return self.instance
            command = ClientUpdateCommand(
                id=self.instance.id,
                name=data.get("name"),
                phone=data.get("phone"),
                email=data.get("email"),
                is_company=data.get("is_company"),
                note=data.get("note"),
            )
            updated = self._service.update(command)
            self.instance = updated
            return updated

        similar = self._service.find_similar(data.get("name", ""))
        if similar:
            names = ", ".join(client.name for client in similar[:3])
            if not confirm(
                f"Найдены похожие клиенты: {names}\nСоздать нового?",
                title="Возможный дубликат",
            ):
                return None

        command = ClientCreateCommand(
            name=data.get("name", ""),
            phone=data.get("phone"),
            email=data.get("email"),
            is_company=data.get("is_company", False),
            note=data.get("note"),
        )
        created = self._service.create(command)
        self.instance = created
        return created

    def _is_unchanged(self, data: dict) -> bool:
        if not isinstance(self.instance, ClientDetailsDTO):
            return False
        return all(getattr(self.instance, key) == value for key, value in data.items())
