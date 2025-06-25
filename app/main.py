from fastapi import FastAPI

from .api.router import router as api_router
from .web.router import router as web_router
from .db import engine
from .models import Base

app = FastAPI()
Base.metadata.create_all(bind=engine)
app.include_router(api_router, prefix="/api")
app.include_router(web_router)

@app.get("/ping")
def ping():
    return {"message": "pong"}
