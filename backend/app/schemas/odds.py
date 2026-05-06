# backend/app/schemas/odds.py

from datetime import datetime

from pydantic import BaseModel


class MatchOddsCreate(BaseModel):
    match_id: int
    provider: str = "manual"
    bookmaker: str | None = None
    market: str
    selection: str
    odds: float


class MatchOddsResponse(BaseModel):
    id: int
    match_id: int
    provider: str
    bookmaker: str | None
    market: str
    selection: str
    odds: float
    retrieved_at: datetime

    model_config = {
        "from_attributes": True
    }