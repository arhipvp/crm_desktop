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

def list_clients(session: Session) -> list[Client]:
    return session.query(Client).filter_by(is_deleted=False).order_by(Client.name).all()


def update_client(session: Session, client_id: int, **kwargs) -> Client | None:
    client = session.get(Client, client_id)
    if not client:
        return None
    for key, value in kwargs.items():
        setattr(client, key, value)
    session.commit()
    session.refresh(client)
    return client


def delete_client(session: Session, client_id: int) -> bool:
    client = session.get(Client, client_id)
    if not client:
        return False
    session.delete(client)
    session.commit()
    return True
