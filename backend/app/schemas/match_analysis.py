# backend/app/schemas/match_analysis.py

from datetime import date
from pydantic import BaseModel


class MatchPredictionResponse(BaseModel):
    market: str
    predicted_label: str
    confidence: float

    odds: float | None
    implied_probability: float | None
    value_score: float | None

    model_name: str


class TeamFormGame(BaseModel):
    opponent: str
    result: str

    goals_for: int
    goals_against: int

    kickoff_date: date


class TeamFormResponse(BaseModel):
    team: str

    wins: int
    draws: int
    losses: int

    goals_for_avg: float
    goals_against_avg: float

    recent_games: list[TeamFormGame]


class MatchInfoResponse(BaseModel):
    id: int

    league: str
    kickoff_date: date

    home_team: str
    away_team: str

    home_goals: int | None
    away_goals: int | None

    home_sot: int
    home_corners: int
    home_possession: float

    away_sot: int
    away_corners: int
    away_possession: float


class H2HResponse(BaseModel):
    games_played: int

    home_team_wins: int
    away_team_wins: int
    draws: int

    average_goals: float

    recent_games: list[dict]
    
class MarketProbabilityResponse(BaseModel):
    market: str
    predicted_label: str
    probability: float

    odds: float | None
    implied_probability: float | None
    value_score: float | None

    model_name: str


class MatchAnalysisResponse(BaseModel):
    match: MatchInfoResponse

    best_prediction: MatchPredictionResponse | None

    predictions: list[MatchPredictionResponse]

    home_form: TeamFormResponse
    away_form: TeamFormResponse

    head_to_head: H2HResponse

    risk_level: str
    
    market_probabilities: list[MarketProbabilityResponse]
    
