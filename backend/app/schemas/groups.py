# backend/app/schemas/groups.py

from pydantic import BaseModel


class GroupCreateResponse(BaseModel):
    slate: str
    group_averages: dict[str, float]


class GroupItemResponse(BaseModel):
    group_name: str
    prediction_id: int
    match_id: int
    home_team: str
    away_team: str
    market: str
    predicted_label: str
    confidence: float