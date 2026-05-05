# backend/app/routers/ml_router.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.ml.train_football import train_football_home_win_model


router = APIRouter(prefix="/ml", tags=["ML"])


@router.post("/train-football")
def train_football_model(
    session: Session = Depends(get_session),
):
    train_football_home_win_model(session)

    return {
        "message": "Football home-win model trained successfully."
    }