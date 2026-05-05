# backend/app/routers/ml_router.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.ml.train_football import (
    train_all_football_models,
    train_football_home_win_model,
    train_football_over_2_5_model,
)


router = APIRouter(prefix="/ml", tags=["ML"])


@router.post("/train-football/home-win")
def train_football_home_win(
    session: Session = Depends(get_session),
):
    train_football_home_win_model(session)

    return {
        "message": "Football home-win model trained successfully."
    }


@router.post("/train-football/over-2-5")
def train_football_over_2_5(
    session: Session = Depends(get_session),
):
    train_football_over_2_5_model(session)

    return {
        "message": "Football over 2.5 goals model trained successfully."
    }


@router.post("/train-football/all")
def train_all_football(
    session: Session = Depends(get_session),
):
    train_all_football_models(session)

    return {
        "message": "All football models trained successfully."
    }