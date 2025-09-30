import pytest

from services.clients.dto import ClientDetailsDTO
from ui.forms.client_form import ClientForm


@pytest.mark.usefixtures("qapp")
def test_client_form_create_uses_app_service(stub_client_app_service):
    stub = stub_client_app_service
    stub.similar = []
    stub.next_created = ClientDetailsDTO(
        id=1,
        name="Новый клиент",
        phone="+79001234567",
        email=None,
        is_company=False,
        note=None,
        drive_folder_path=None,
        drive_folder_link=None,
        is_deleted=False,
        deals_count=0,
        policies_count=0,
    )

    form = ClientForm()
    assert form.name_edit is not None
    assert form.phone_edit is not None

    form.name_edit.setText("Новый клиент")
    form.phone_edit.setText("+7 (900) 123-45-67")

    saved = form.save_data()

    assert saved == stub.next_created
    assert stub.created_commands
    assert stub.created_commands[0].name == "Новый клиент"


@pytest.mark.usefixtures("qapp")
def test_client_form_update_uses_app_service(stub_client_app_service):
    stub = stub_client_app_service
    original = ClientDetailsDTO(
        id=10,
        name="Текущий клиент",
        phone="+79001112233",
        email="old@example.com",
        is_company=False,
        note="Заметка",
        drive_folder_path=None,
        drive_folder_link=None,
        is_deleted=False,
        deals_count=1,
        policies_count=2,
    )
    updated = ClientDetailsDTO(
        id=10,
        name="Обновлённый клиент",
        phone="+79001112233",
        email="new@example.com",
        is_company=True,
        note="Заметка",
        drive_folder_path=None,
        drive_folder_link=None,
        is_deleted=False,
        deals_count=1,
        policies_count=2,
    )
    stub.next_updated = updated

    form = ClientForm(original)
    form.name_edit.setText("Обновлённый клиент")
    form.email_edit.setText("new@example.com")
    form.company_checkbox.setChecked(True)

    saved = form.save_data()

    assert saved == updated
    assert stub.updated_commands
    command = stub.updated_commands[0]
    assert command.id == original.id
    assert command.name == "Обновлённый клиент"
    assert command.email == "new@example.com"
    assert command.is_company is True
