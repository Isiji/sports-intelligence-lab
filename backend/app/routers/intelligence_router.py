# backend/app/routers/intelligence_router.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
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