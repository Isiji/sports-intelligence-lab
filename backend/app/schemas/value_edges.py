# backend/app/schemas/value_edges.py

from datetime import date

from pydantic import BaseModel


class ValueEdgeResponse(BaseModel):
    id: int
    slate: str
    match_id: int

    league: str

    home_team: str
    away_team: str

    market: str
    predicted_label: str

    confidence: float

    odds: float | None
    implied_probability: float | None
    value_score: float | None

    model_name: str

    kickoff_date: date