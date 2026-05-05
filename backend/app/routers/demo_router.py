# backend/app/routers/demo_router.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.ingest.demo_results import simulate_demo_results
from app.ingest.demo_seed import seed_demo_data


router = APIRouter(prefix="/demo", tags=["Demo"])


@router.post("/seed")
def seed_demo(
    session: Session = Depends(get_session),
):
    seed_demo_data(session)

    return {
        "message": "Demo football data seeded."
    }


@router.post("/simulate-results")
def simulate_results(
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    updated = simulate_demo_results(session=session, limit=limit)

    return {
        "message": "Demo results simulated.",
        "updated_matches": updated,
    }