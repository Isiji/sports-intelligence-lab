# backend/app/routers/ml_router.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.ml.train_football import train_all_football_models


router = APIRouter(prefix="/ml", tags=["ML"])


@router.post("/train-football/all")
def train_all_football(
    session: Session = Depends(get_session),
):
    train_all_football_models(session)

    return {
        "message": "All football models trained successfully."
    }