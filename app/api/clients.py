from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Client
from ..services.client_service import (
    create_client,
    get_client,
    update_client,
    delete_client,
    list_clients,
)
from ..schemas import ClientCreate, ClientRead, ClientUpdate

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("/", response_model=list[ClientRead])
def read_clients(session: Session = Depends(get_session)):
    return list_clients(session)


@router.post("/", response_model=ClientRead)
def add_client(client_in: ClientCreate, session: Session = Depends(get_session)):
    client = create_client(session, **client_in.model_dump())
    return client


@router.get("/{client_id}", response_model=ClientRead)
def read_client(client_id: int, session: Session = Depends(get_session)):
    client = get_client(session, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.put("/{client_id}", response_model=ClientRead)
def edit_client(
    client_id: int,
    client_in: ClientUpdate,
    session: Session = Depends(get_session),
):
    client = update_client(session, client_id, **client_in.model_dump(exclude_none=True))
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.delete("/{client_id}")
def remove_client(client_id: int, session: Session = Depends(get_session)):
    if not delete_client(session, client_id):
        raise HTTPException(status_code=404, detail="Client not found")
    return {"status": "deleted"}
