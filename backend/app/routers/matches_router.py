# backend/app/routers/matches_router.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Match, Prediction
from app.db.session import get_session
from app.schemas.matches import MatchResponse
from app.schemas.predictions import PredictionResponse


router = APIRouter(prefix="/matches", tags=["Matches"])


@router.get("", response_model=list[MatchResponse])
def list_matches(
    status: str = Query("all", pattern="^(all|played|upcoming)$"),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    query = select(Match).order_by(Match.kickoff_date.desc())

    if status == "played":
        query = query.where(Match.home_goals.isnot(None), Match.away_goals.isnot(None))
    elif status == "upcoming":
        query = query.where(Match.home_goals.is_(None), Match.away_goals.is_(None))

    query = query.limit(limit)

    return list(session.scalars(query))


@router.get("/search", response_model=list[MatchResponse])
def search_matches(
    q: str = Query(..., min_length=2),
    limit: int = Query(30, ge=1, le=100),
    session: Session = Depends(get_session),
):
    query = (
        select(Match)
        .where(
            or_(
                Match.home_team.ilike(f"%{q}%"),
                Match.away_team.ilike(f"%{q}%"),
                Match.league.ilike(f"%{q}%"),
            )
        )
        .order_by(Match.kickoff_date.desc())
        .limit(limit)
    )

    return list(session.scalars(query))


@router.get("/{match_id}", response_model=MatchResponse)
def get_match(
    match_id: int,
    session: Session = Depends(get_session),
):
    match = session.get(Match, match_id)

    if match is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Match not found.")

    return match


# backend/app/routers/matches_router.py

@router.get("/{match_id}/predictions", response_model=list[PredictionResponse])
def get_match_predictions(
    match_id: int,
    slate: str | None = Query(None),
    session: Session = Depends(get_session),
):
    from app.utils.slate import resolve_slate

    selected_slate = resolve_slate(slate)

    query = (
        select(Prediction)
        .where(
            Prediction.match_id == match_id,
            Prediction.slate == selected_slate,
        )
        .order_by(Prediction.confidence.desc())
    )

    return list(session.scalars(query))