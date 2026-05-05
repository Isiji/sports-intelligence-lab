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
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class PredictionRunResponse(BaseModel):
    slate: str
    inserted_predictions: int