# backend/app/schemas/backtests.py

from datetime import datetime

from pydantic import BaseModel


class BacktestRunResponse(BaseModel):
    id: int
    slate: str
    model_name: str
    created_at: datetime
    overall_accuracy: float
    settled_predictions: int

    model_config = {
        "from_attributes": True
    }


class GroupBacktestResponse(BaseModel):
    group_name: str
    picks: int
    accuracy: float