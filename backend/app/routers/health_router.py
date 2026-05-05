# backend/app/routers/health_router.py

from fastapi import APIRouter

from app.config import settings


router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
def health_check() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.env,
    }