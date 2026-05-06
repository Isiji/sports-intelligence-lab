# backend/app/schemas/dashboard.py

from pydantic import BaseModel


class GamePrediction(BaseModel):
    home_team: str
    away_team: str
    market: str
    predicted_label: str
    confidence: float
    odds: float | None = None
    value_score: float | None = None


class GroupSummary(BaseModel):
    group_name: str
    average_confidence: float
    cumulative_odds: float
    games: list[GamePrediction]


class DashboardResponse(BaseModel):
    slate: str
    groups: list[GroupSummary]