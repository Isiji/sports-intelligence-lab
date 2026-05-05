# backend/app/routers/predictions_router.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Prediction
from app.db.session import get_session
from app.ml.predict_football import predict_football_home_win
from app.schemas.predictions import PredictionResponse, PredictionRunResponse


router = APIRouter(prefix="/predictions", tags=["Predictions"])


@router.get("", response_model=list[PredictionResponse])
def list_predictions(
    slate: str = Query("demo"),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    query = (
        select(Prediction)
        .where(Prediction.slate == slate)
        .order_by(Prediction.confidence.desc(), Prediction.id.asc())
        .limit(limit)
    )

    return list(session.scalars(query))


@router.post("/run-football", response_model=PredictionRunResponse)
def run_football_predictions(
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