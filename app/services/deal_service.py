from datetime import date
from sqlalchemy.orm import Session

from ..models import Deal, Client


def create_deal(
    session: Session,
    client_id: int,
    start_date: date,
    description: str,
    **kwargs,
) -> Deal:
    client = session.get(Client, client_id)
    if not client:
        raise ValueError("Client not found")
    deal = Deal(
        client=client,
        start_date=start_date,
        description=description,
        **kwargs,
    )
    session.add(deal)
    session.commit()
    session.refresh(deal)
    return deal


def get_deal(session: Session, deal_id: int) -> Deal | None:
    return session.get(Deal, deal_id)
