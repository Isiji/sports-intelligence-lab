# backend/app/schemas/predictions.py

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PredictionResponse(BaseModel):
    id: int
    slate: str
    match_id: int
    sport: str
    model_name: str
    market: str
    predicted_label: str
    confidence: float

    odds: float | None = None
    implied_probability: float | None = None
    value_score: float | None = None

    odds_bookmaker: str | None = None
    odds_market: str | None = None
    odds_selection: str | None = None
    odds_retrieved_at: datetime | None = None
    odds_match_quality: str | None = None

    execution_market: str | None = None
    execution_selection: str | None = None
    execution_family: str | None = None
    execution_line: float | None = None

    bookmaker_locality: str | None = None
    local_realism_score: float | None = None
    execution_score: float | None = None
    survivability_score: float | None = None
    execution_ready: bool | None = None

    execution_reasons: list[Any] | None = Field(default_factory=list)
    market_alternatives: Any | None = None

    is_correct: bool | None = None
    result_label: str | None = None
    profit_loss: float | None = None
    stake: float | None = None
    settled_at: datetime | None = None
    closing_odds: float | None = None
    clv: float | None = None

    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class PredictionRunResponse(BaseModel):
    slate: str
    inserted_predictions: int