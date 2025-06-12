"""Minimal FastAPI application working alongside the existing desktop app."""

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from database.sa import init_engine, engine, SessionLocal
from database import sa_models as models

# Initialize engine and create tables
init_engine()
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="CRM API")


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/clients")
def list_clients(db: Session = Depends(get_db)):
    clients = db.query(models.Client).filter(models.Client.is_deleted == False).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "phone": c.phone,
            "email": c.email,
        }
        for c in clients
    ]


@app.post("/clients")
def create_client(data: dict, db: Session = Depends(get_db)):
    name = data.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    client = models.Client(name=name)
    for field in ["phone", "email", "is_company", "note"]:
        if field in data:
            setattr(client, field, data[field])
    db.add(client)
    db.commit()
    db.refresh(client)
    return {
        "id": client.id,
        "name": client.name,
        "phone": client.phone,
        "email": client.email,
    }

