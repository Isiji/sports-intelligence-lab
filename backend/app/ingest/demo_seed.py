# backend/app/ingest/demo_seed.py

from datetime import date, timedelta
import random

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Match, Prediction, PredictionGroupItem, TeamMatchStat


TEAMS = [
    "Arsenal",
    "Liverpool",
    "Chelsea",
    "Newcastle",
    "Brighton",
    "Tottenham",
    "Aston Villa",
    "West Ham",
]


def seed_demo_data(
    session: Session,
    historical_matches: int = 120,
    upcoming_matches: int = 20,
) -> None:
    random.seed(settings.random_seed)

    session.execute(delete(PredictionGroupItem))
    session.execute(delete(Prediction))
    session.execute(delete(TeamMatchStat))
    session.execute(delete(Match))

    start_date = date.today() - timedelta(days=historical_matches)

    for idx in range(historical_matches + upcoming_matches):
        home_team, away_team = random.sample(TEAMS, 2)
        kickoff_date = start_date + timedelta(days=idx)

        is_played = idx < historical_matches

        home_goals = random.randint(0, 4) if is_played else None
        away_goals = random.randint(0, 4) if is_played else None

        match = Match(
            sport="football",
            provider="internal",
            provider_fixture_id=f"demo-{idx}",
            season=2026,
            league="Demo Premier League",
            home_team=home_team,
            away_team=away_team,
            kickoff_date=kickoff_date,
            home_goals=home_goals,
            away_goals=away_goals,
        )

        session.add(match)
        session.flush()

        home_stats = _build_team_stats(
            match_id=match.id,
            team=home_team,
            is_home=1,
            goals=home_goals,
        )

        away_stats = _build_team_stats(
            match_id=match.id,
            team=away_team,
            is_home=0,
            goals=away_goals,
        )

        session.add(home_stats)
        session.add(away_stats)

    session.commit()


def _build_team_stats(
    match_id: int,
    team: str,
    is_home: int,
    goals: int | None,
) -> TeamMatchStat:
    estimated_goals = goals if goals is not None else random.randint(0, 3)

    return TeamMatchStat(
        match_id=match_id,
        team=team,
        is_home=is_home,
        goals=estimated_goals,
        corners=random.randint(1, 10),
        shots_on_target=max(1, estimated_goals + random.randint(1, 6)),
        possession=round(random.uniform(35, 65), 2),
        fouls=random.randint(6, 18),
        cards=random.randint(0, 5),
        keeper_saves=random.randint(0, 8),
    )