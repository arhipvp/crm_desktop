from dataclasses import dataclass
from database.models import Client


@dataclass
class ClientDTO:
    id: int
    name: str
    phone: str | None = None
    email: str | None = None
    is_company: bool = False
    note: str | None = None
    drive_folder_path: str | None = None
    drive_folder_link: str | None = None

    @classmethod
    def from_model(cls, client: Client) -> "ClientDTO":
        return cls(
            id=client.id,
            name=client.name,
            phone=client.phone,
            email=client.email,
            is_company=client.is_company,
            note=client.note,
            drive_folder_path=client.drive_folder_path,
            drive_folder_link=client.drive_folder_link,
        )
