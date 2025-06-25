from sqlalchemy.orm import Session

from ..models import Client


def create_client(session: Session, **kwargs) -> Client:
    client = Client(**kwargs)
    session.add(client)
    session.commit()
    session.refresh(client)
    return client


def get_client(session: Session, client_id: int) -> Client | None:
    return session.get(Client, client_id)
