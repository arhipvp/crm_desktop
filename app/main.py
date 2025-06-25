from fastapi import FastAPI

from .api.router import router as api_router

app = FastAPI()
app.include_router(api_router, prefix="/api")

@app.get("/ping")
def ping():
    return {"message": "pong"}
