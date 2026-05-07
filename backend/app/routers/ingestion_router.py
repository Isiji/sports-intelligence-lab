from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.ingest.football_ingestion import ingest_fixtures_for_date
from app.ingest.football_odds_ingestion import (
    ingest_odds_for_fixture,
    ingest_odds_for_upcoming_matches,
)
from app.ingest.football_stats_ingestion import (
    ingest_fixture_statistics,
    ingest_missing_statistics,
)


router = APIRouter(
    prefix="/ingestion",
    tags=["Ingestion"],
)


@router.post("/football/fixtures/date")
def ingest_football_fixtures_by_date(
    date_value: date = Query(...),
    session: Session = Depends(get_session),
):
    return ingest_fixtures_for_date(
        session=session,
        date_value=date_value,
    )


@router.post("/football/odds/match/{match_id}")
def ingest_football_odds_for_match(
    match_id: int,
    session: Session = Depends(get_session),
):
    return ingest_odds_for_fixture(
        session=session,
        match_id=match_id,
    )


@router.post("/football/odds/upcoming")
def ingest_football_odds_for_upcoming(
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    return ingest_odds_for_upcoming_matches(
        session=session,
        limit=limit,
    )
    
    
    
@router.post("/football/stats/match/{match_id}")
def ingest_football_stats_for_match(
    match_id: int,
    force: bool = Query(False),
    session: Session = Depends(get_session),
):
    return ingest_fixture_statistics(
        session=session,
        match_id=match_id,
        force=force,
    )


@router.post("/football/stats/missing")
def ingest_missing_football_stats(
    limit: int = Query(50, ge=1, le=500),
    force: bool = Query(False),
    session: Session = Depends(get_session),
):
    return ingest_missing_statistics(
        session=session,
        limit=limit,
        force=force,
    )