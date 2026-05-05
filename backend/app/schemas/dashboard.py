# backend/app/schemas/dashboard.py

from pydantic import BaseModel


class GamePrediction(BaseModel):
    home_team: str
    away_team: str
    predicted_label: str
    confidence: float


class GroupSummary(BaseModel):
    group_name: str
    average_confidence: float
    games: list[GamePrediction]


class DashboardResponse(BaseModel):
    slate: str
    groups: list[GroupSummary]