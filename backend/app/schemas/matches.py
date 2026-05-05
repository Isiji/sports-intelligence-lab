# backend/app/schemas/matches.py

from datetime import date

from pydantic import BaseModel


class MatchResponse(BaseModel):
    id: int
    sport: str
    provider: str
    provider_fixture_id: str | None
    season: int | None
    league: str
    home_team: str
    away_team: str
    kickoff_date: date
    home_goals: int | None
    away_goals: int | None

    model_config = {
        "from_attributes": True
    }