from pydantic import BaseModel


class ClientBase(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    is_company: bool | None = None
    note: str | None = None


class ClientCreate(ClientBase):
    name: str


class ClientUpdate(ClientBase):
    pass


class ClientRead(ClientBase):
    id: int
    drive_folder_path: str | None = None
    drive_folder_link: str | None = None
    is_deleted: bool

    class Config:
        from_attributes = True
