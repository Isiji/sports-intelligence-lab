# backend/app/api/research_routes.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.reports.competition_coverage import build_competition_coverage_report
from app.reports.match_report import build_match_report, search_matches
from app.reports.prediction_performance import build_prediction_performance_report


router = APIRouter(prefix="/research", tags=["Research Dashboard"])


@router.get("/coverage")
def get_competition_coverage(
    limit: int = Query(100, ge=1, le=1000),
    session: Session = Depends(get_db),
):
    return build_competition_coverage_report(
        session=session,
        limit=limit,
    )


@router.get("/performance")
def get_prediction_performance(
    slate: str | None = None,
    session: Session = Depends(get_db),
):
    return build_prediction_performance_report(
        session=session,
        slate=slate,
    )


@router.get("/matches/search")
def search_research_matches(
    q: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_db),
):
    return {
        "query": q,
        "matches": search_matches(
            session=session,
            query=q,
            limit=limit,
        ),
    }


@router.get("/matches/{match_id}/report")
def get_match_research_report(
    match_id: int,
    session: Session = Depends(get_db),
):
    try:
        return build_match_report(
            session=session,
            match_id=match_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc