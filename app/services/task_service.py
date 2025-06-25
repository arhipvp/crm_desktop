from datetime import date, datetime
from sqlalchemy.orm import Session

from ..models import Task, Deal, Policy


def create_task(
    session: Session,
    title: str,
    due_date: date,
    deal_id: int | None = None,
    policy_id: int | None = None,
    **kwargs,
) -> Task:
    deal = session.get(Deal, deal_id) if deal_id else None
    policy = session.get(Policy, policy_id) if policy_id else None
    task = Task(
        title=title,
        due_date=due_date,
        deal=deal,
        policy=policy,
        **kwargs,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def get_task(session: Session, task_id: int) -> Task | None:
    return session.get(Task, task_id)
