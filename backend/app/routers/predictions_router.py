# backend/app/routers/predictions_router.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Prediction
from app.db.session import get_session
from app.ml.predict_football import (
    predict_all_football_markets,
    predict_football_home_win,
    predict_football_over_2_5,
)
from app.schemas.predictions import PredictionResponse, PredictionRunResponse


router = APIRouter(prefix="/predictions", tags=["Predictions"])


@router.get("", response_model=list[PredictionResponse])
def list_predictions(
    slate: str = Query("demo"),
    limit: int = Query(100, ge=1, le=300),
    session: Session = Depends(get_session),
):
    query = (
        select(Prediction)
        .where(Prediction.slate == slate)
        .order_by(Prediction.confidence.desc(), Prediction.id.asc())
        .limit(limit)
    )

    return list(session.scalars(query))


@router.post("/run-football/home-win", response_model=PredictionRunResponse)
def run_football_home_win_predictions(
    slate: str = Query("demo"),
    limit: int = Query(16, ge=1, le=50),
    session: Session = Depends(get_session),
):
    inserted = predict_football_home_win(
        session=session,
        slate=slate,
        limit=limit,
    )

    return PredictionRunResponse(
        slate=slate,
        inserted_predictions=inserted,
    )


@router.post("/run-football/over-2-5", response_model=PredictionRunResponse)
def run_football_over_2_5_predictions(
    slate: str = Query("demo"),
    limit: int = Query(16, ge=1, le=50),
    session: Session = Depends(get_session),
):
    inserted = predict_football_over_2_5(
        session=session,
        slate=slate,
        limit=limit,
    )

    return PredictionRunResponse(
        slate=slate,
        inserted_predictions=inserted,
    )


@router.post("/run-football/all", response_model=PredictionRunResponse)
def run_all_football_predictions(
    slate: str = Query("demo"),
    limit: int = Query(16, ge=1, le=50),
    session: Session = Depends(get_session),
):
    inserted = predict_all_football_markets(
        session=session,
        slate=slate,
        limit=limit,
    )

    return PredictionRunResponse(
        slate=slate,
        inserted_predictions=inserted,
    )