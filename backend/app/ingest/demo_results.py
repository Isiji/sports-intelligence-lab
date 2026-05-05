# backend/app/ingest/demo_results.py

from random import randint, seed

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Match


def simulate_demo_results(session: Session, limit: int = 20) -> int:
    """
    Add fake final scores to upcoming demo matches.

    This is only for local learning/testing so that backtesting can work
    without waiting for real matches to finish.
    """
    seed(settings.random_seed + 100)

    matches = list(
        session.scalars(
            select(Match)
            .where(
                Match.provider == "internal",
                Match.home_goals.is_(None),
                Match.away_goals.is_(None),
            )
            .order_by(Match.kickoff_date.asc())
            .limit(limit)
        )
    )

    updated = 0

    for match in matches:
        match.home_goals = randint(0, 4)
        match.away_goals = randint(0, 4)
        updated += 1

    session.commit()

    return updated