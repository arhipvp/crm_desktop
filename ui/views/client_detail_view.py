from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from ui.base.base_detail_view import BaseDetailView
from ui.common.message_boxes import confirm, show_error, show_info

from services.clients.client_app_service import client_app_service
from services.clients.dto import ClientDetailsDTO
from ui.forms.client_form import ClientForm


class ClientDetailView(BaseDetailView):
    """Детальная карточка клиента, работающая с DTO."""

    def __init__(self, client: ClientDetailsDTO, parent=None):
        self._service = client_app_service
        super().__init__(client, parent=parent)

    def get_title(self) -> str:
        return self.instance.name

    def populate_info_tab(self):  # type: ignore[override]
        self._clear_layout(self.key_facts_layout)
        self._clear_layout(self.info_layout)

        info_fields = [
            ("Имя", self.instance.name),
            ("Телефон", self.instance.phone),
            ("Email", self.instance.email),
            ("Компания", "Да" if self.instance.is_company else "Нет"),
            ("Заметки", self.instance.note),
            ("Папка", self.instance.drive_folder_path or self.instance.drive_folder_link),
            ("Активен", "Нет" if self.instance.is_deleted else "Да"),
            ("Сделок", str(self.instance.deals_count)),
            ("Полисов", str(self.instance.policies_count)),
        ]

        for label, value in info_fields:
            text = f"<b>{label}:</b> {value if value else '—'}"
            summary_label = QLabel(text)
            summary_label.setTextFormat(Qt.RichText)
            summary_label.setWordWrap(True)
            self.key_facts_layout.addWidget(summary_label)

            detail_label = QLabel(text)
            detail_label.setTextFormat(Qt.RichText)
            detail_label.setWordWrap(True)
            self.info_layout.addWidget(detail_label)

        self.key_facts_layout.addStretch()
        self.info_layout.addStretch()

    def edit(self):  # type: ignore[override]
        form = ClientForm(self.instance, parent=self)
        if not form.exec():
            return

        updated = form.saved_instance or self._service.get_detail(self.instance.id)
        self.instance = updated
        self.populate_info_tab()
        self.title_label.setText(self.get_title())

    def delete(self):  # type: ignore[override]
        if not confirm("Пометить клиента удалённым?"):
            return
        try:
            self._service.delete_many([self.instance.id])
        except Exception as exc:  # noqa: BLE001
            show_error(str(exc))
            return
        show_info("Клиент помечен удалённым")
        self.accept()
