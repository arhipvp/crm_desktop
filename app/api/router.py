from fastapi import APIRouter

from .clients import router as clients_router

router = APIRouter()
router.include_router(clients_router)

@router.get("/status")
def status():
    return {"status": "ok"}
