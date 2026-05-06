# backend/app/routers/predictions_router.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Prediction
from app.db.session import get_session
from app.features.football_features import MARKET_TARGETS
from app.ml.predict_football import predict_all_football_markets, predict_football_market
from app.schemas.predictions import PredictionResponse, PredictionRunResponse


router = APIRouter(prefix="/predictions", tags=["Predictions"])


@router.get("", response_model=list[PredictionResponse])
def list_predictions(
    slate: str = Query("demo"),
    market: str | None = Query(None),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    query = (
        select(Prediction)
        .where(
            Prediction.slate == slate,
            Prediction.confidence >= min_confidence,
        )
        .order_by(Prediction.confidence.desc(), Prediction.id.asc())
        .limit(limit)
    )

    if market:
        query = query.where(Prediction.market == market)

    return list(session.scalars(query))


@router.post("/run-football/all", response_model=PredictionRunResponse)
def run_all_football_predictions(
    slate: str = Query("demo"),
    limit: int = Query(30, ge=1, le=100),
    min_confidence: float = Query(0.6, ge=0.5, le=0.99),
    session: Session = Depends(get_session),
):
    inserted = predict_all_football_markets(
        session=session,
        slate=slate,
        limit=limit,
        min_confidence=min_confidence,
    )

    return PredictionRunResponse(
        slate=slate,
        inserted_predictions=inserted,
    )


@router.post("/run-football/{market}", response_model=PredictionRunResponse)
def run_football_market_predictions(
    market: str,
    slate: str = Query("demo"),
    limit: int = Query(30, ge=1, le=100),
    min_confidence: float = Query(0.6, ge=0.5, le=0.99),
    session: Session = Depends(get_session),
):
    if market not in MARKET_TARGETS:
        raise HTTPException(status_code=400, detail=f"Unsupported market: {market}")

    inserted = predict_football_market(
        session=session,
        slate=slate,
        market=market,
        limit=limit,
        min_confidence=min_confidence,
    )

    return PredictionRunResponse(
        slate=slate,
        inserted_predictions=inserted,
    )