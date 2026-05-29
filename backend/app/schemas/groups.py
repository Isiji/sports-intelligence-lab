# backend/app/schemas/groups.py

from typing import Any

from pydantic import BaseModel


class GroupCreateResponse(BaseModel):
    slate: str
    group_summaries: dict[str, dict[str, Any]]


class GroupItemResponse(BaseModel):
    group_name: str
    prediction_id: int
    match_id: int

    league: str | None = None
    kickoff_eat: str | None = None

    home_team: str
    away_team: str

    market: str
    predicted_label: str
    confidence: float

    odds: float | None = None
    value_score: float | None = None

    execution_market: str | None = None
    execution_selection: str | None = None
    execution_score: float | None = None
    survivability_score: float | None = None
    local_realism_score: float | None = None
    execution_ready: bool | None = None

    odds_bookmaker: str | None = None
    bookmaker_locality: str | None = None
    execution_reasons: list[Any] | None = None