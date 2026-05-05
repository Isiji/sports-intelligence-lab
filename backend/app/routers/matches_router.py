# backend/app/routers/matches_router.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Match
from app.db.session import get_session
from app.schemas.matches import MatchResponse


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