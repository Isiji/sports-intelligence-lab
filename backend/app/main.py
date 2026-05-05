# backend/app/main.py

from fastapi import FastAPI

from app.config import settings
from app.routers.health_router import router as health_router


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Sports ML research lab for predictions, grouping, and backtesting.",
)

app.include_router(health_router)


@app.get("/")
def root() -> dict:
    return {
        "message": "Welcome to Sports Intelligence Lab",
        "docs": "/docs",
    }