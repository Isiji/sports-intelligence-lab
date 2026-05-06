# backend/app/routers/odds_router.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MatchOdds
from app.db.session import get_session
from app.schemas.odds import MatchOddsCreate, MatchOddsResponse


router = APIRouter(prefix="/odds", tags=["Odds"])


@router.post("", response_model=MatchOddsResponse)
def create_match_odds(
    payload: MatchOddsCreate,
    session: Session = Depends(get_session),
):
    odds = MatchOdds(**payload.model_dump())

    session.add(odds)
    session.commit()
    session.refresh(odds)

    return odds


@router.get("", response_model=list[MatchOddsResponse])
def list_match_odds(
    match_id: int | None = Query(None),
    market: str | None = Query(None),
    limit: int = Query(100, ge=1, le=300),
    session: Session = Depends(get_session),
):
    query = select(MatchOdds).order_by(MatchOdds.retrieved_at.desc())

    if match_id:
        query = query.where(MatchOdds.match_id == match_id)

    if market:
        query = query.where(MatchOdds.market == market)

    query = query.limit(limit)

    return list(session.scalars(query))