# backend/app/routers/intelligence_router.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services.league_intelligence_service import (
    list_league_intelligence,
    rebuild_league_intelligence,
)
from app.services.market_reliability_service import (
    list_market_reliability,
    rebuild_market_reliability,
)
from app.services.stats_quality_service import (
    list_stats_quality_snapshots,
    rebuild_stats_quality_snapshots,
)


router = APIRouter(prefix="/intelligence", tags=["Intelligence"])


@router.post("/stats-quality/rebuild")
def rebuild_stats_quality(
    session: Session = Depends(get_session),
):
    return rebuild_stats_quality_snapshots(session)


@router.get("/stats-quality")
def get_stats_quality(
    limit: int = Query(default=100, ge=1, le=500),
    min_score: float | None = Query(default=None, ge=0.0, le=1.0),
    tier: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    return {
        "items": list_stats_quality_snapshots(
            session=session,
            limit=limit,
            min_score=min_score,
            tier=tier,
        )
    }


@router.post("/leagues/rebuild")
def rebuild_leagues(
    session: Session = Depends(get_session),
):
    return rebuild_league_intelligence(session)


@router.get("/leagues")
def get_leagues(
    limit: int = Query(default=100, ge=1, le=500),
    prediction_allowed: bool | None = Query(default=None),
    training_allowed: bool | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    return {
        "items": list_league_intelligence(
            session=session,
            limit=limit,
            prediction_allowed=prediction_allowed,
            training_allowed=training_allowed,
            risk_level=risk_level,
        )
    }


@router.post("/markets/rebuild")
def rebuild_markets(
    session: Session = Depends(get_session),
):
    return rebuild_market_reliability(session)


@router.get("/markets")
def get_markets(
    limit: int = Query(default=100, ge=1, le=500),
    prediction_allowed: bool | None = Query(default=None),
    tier: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    return {
        "items": list_market_reliability(
            session=session,
            limit=limit,
            prediction_allowed=prediction_allowed,
            tier=tier,
        )
    }