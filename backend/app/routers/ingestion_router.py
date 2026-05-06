from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.ingest.football_ingestion import ingest_fixtures_for_date


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