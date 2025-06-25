from datetime import date
from sqlalchemy.orm import Session

from ..models import Policy, Client, Deal


def create_policy(
    session: Session,
    client_id: int,
    policy_number: str,
    start_date: date,
    deal_id: int | None = None,
    **kwargs,
) -> Policy:
    client = session.get(Client, client_id)
    if not client:
        raise ValueError("Client not found")
    deal = session.get(Deal, deal_id) if deal_id else None
    policy = Policy(
        client=client,
        deal=deal,
        policy_number=policy_number,
        start_date=start_date,
        **kwargs,
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return policy


def get_policy(session: Session, policy_id: int) -> Policy | None:
    return session.get(Policy, policy_id)
