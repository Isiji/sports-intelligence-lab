# backend/app/schemas/predictions.py

from datetime import datetime

from pydantic import BaseModel


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