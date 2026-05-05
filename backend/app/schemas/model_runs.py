# backend/app/schemas/model_runs.py

from datetime import datetime

from pydantic import BaseModel


class ModelTrainingRunResponse(BaseModel):
    id: int
    sport: str
    market: str
    model_name: str
    accuracy: float
    selected: int
    created_at: datetime

    model_config = {
        "from_attributes": True
    }