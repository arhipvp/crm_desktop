from pathlib import Path
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..db import get_session
from ..services.client_service import list_clients, create_client

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)):
    clients = list_clients(session)
    return templates.TemplateResponse("index.html", {"request": request, "clients": clients})

@router.post("/clients", response_class=HTMLResponse)
def add_client(name: str = Form(...), phone: str = Form("") , email: str = Form(""), session: Session = Depends(get_session)):
    create_client(session, name=name, phone=phone or None, email=email or None)
    return RedirectResponse("/", status_code=303)
