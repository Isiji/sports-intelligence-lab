# backend/app/db/models.py

from datetime import date, datetime

from sqlalchemy import Boolean, Date, JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Country(Base):
    __tablename__ = "countries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    code: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    continent: Mapped[str | None] = mapped_column(String(60), nullable=True)


class Competition(Base):
    __tablename__ = "competitions"
    __table_args__ = (
        UniqueConstraint("provider", "provider_competition_id", name="uq_competition_provider_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    sport: Mapped[str] = mapped_column(String(30), default="football", index=True)
    provider: Mapped[str] = mapped_column(String(40), default="api-football", index=True)
    provider_competition_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

    name: Mapped[str] = mapped_column(String(160), index=True)
    country_id: Mapped[int | None] = mapped_column(ForeignKey("countries.id"), nullable=True, index=True)

    competition_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_cup: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("provider", "provider_team_id", name="uq_team_provider_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    provider: Mapped[str] = mapped_column(String(40), default="api-football", index=True)
    provider_team_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

    name: Mapped[str] = mapped_column(String(160), index=True)
    normalized_name: Mapped[str] = mapped_column(String(160), index=True)

    country_id: Mapped[int | None] = mapped_column(ForeignKey("countries.id"), nullable=True, index=True)

    is_national_team: Mapped[bool] = mapped_column(Boolean, default=False)
class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("provider", "provider_fixture_id", name="uq_match_provider_fixture"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    sport: Mapped[str] = mapped_column(String(30), default="football", index=True)
    provider: Mapped[str] = mapped_column(String(30), default="internal", index=True)
    provider_fixture_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

    season: Mapped[int | None] = mapped_column(Integer, nullable=True)
    league: Mapped[str] = mapped_column(String(120), index=True)

    home_team: Mapped[str] = mapped_column(String(120), index=True)
    away_team: Mapped[str] = mapped_column(String(120), index=True)

    kickoff_date: Mapped[date] = mapped_column(Date, index=True)

    home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)

    competition_id: Mapped[int | None] = mapped_column(ForeignKey("competitions.id"), nullable=True, index=True)

    home_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True, index=True)
    away_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(40), default="scheduled", index=True)
    round_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    kickoff_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    is_finished: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_postponed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    has_stats: Mapped[bool] = mapped_column(Boolean, default=False)
    has_odds: Mapped[bool] = mapped_column(Boolean, default=False)
    is_valid_for_training: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
class TeamMatchStat(Base):
    __tablename__ = "team_match_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)

    team: Mapped[str] = mapped_column(String(120), index=True)
    is_home: Mapped[int] = mapped_column(Integer)

    goals: Mapped[int] = mapped_column(Integer, default=0)
    corners: Mapped[int] = mapped_column(Integer, default=0)
    shots_on_target: Mapped[int] = mapped_column(Integer, default=0)
    possession: Mapped[float] = mapped_column(Float, default=0.0)
    fouls: Mapped[int] = mapped_column(Integer, default=0)
    cards: Mapped[int] = mapped_column(Integer, default=0)
    keeper_saves: Mapped[int] = mapped_column(Integer, default=0)

    source: Mapped[str] = mapped_column(String(40), default="placeholder", index=True)
    is_real: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    raw_stats_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MatchOdds(Base):
    __tablename__ = "match_odds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)

    provider: Mapped[str] = mapped_column(String(40), default="manual", index=True)
    bookmaker: Mapped[str | None] = mapped_column(String(80), nullable=True)

    market: Mapped[str] = mapped_column(String(80), index=True)
    selection: Mapped[str] = mapped_column(String(80), index=True)

    odds: Mapped[float] = mapped_column(Float)

    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    slate: Mapped[str] = mapped_column(String(100), index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)

    sport: Mapped[str] = mapped_column(String(30), default="football", index=True)
    model_name: Mapped[str] = mapped_column(String(80), default="football_baseline_v1")
    market: Mapped[str] = mapped_column(String(80), default="home_win", index=True)

    predicted_label: Mapped[str] = mapped_column(String(80))
    confidence: Mapped[float] = mapped_column(Float)

    odds: Mapped[float | None] = mapped_column(Float, nullable=True)
    implied_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PredictionGroupItem(Base):
    __tablename__ = "prediction_group_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    slate: Mapped[str] = mapped_column(String(100), index=True)
    group_name: Mapped[str] = mapped_column(String(30), index=True)

    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id"), index=True)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    slate: Mapped[str] = mapped_column(String(100), index=True)
    model_name: Mapped[str] = mapped_column(String(80), default="football_baseline_v1")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    overall_accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    settled_predictions: Mapped[int] = mapped_column(Integer, default=0)


class ApiCallLog(Base):
    __tablename__ = "api_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    provider: Mapped[str] = mapped_column(String(40), index=True)
    endpoint: Mapped[str] = mapped_column(String(120))

    called_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ModelTrainingRun(Base):
    __tablename__ = "model_training_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    sport: Mapped[str] = mapped_column(String(30), default="football", index=True)
    market: Mapped[str] = mapped_column(String(80), index=True)
    model_name: Mapped[str] = mapped_column(String(120), index=True)

    accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    precision: Mapped[float] = mapped_column(Float, default=0.0)
    recall: Mapped[float] = mapped_column(Float, default=0.0)
    f1: Mapped[float] = mapped_column(Float, default=0.0)
    log_loss: Mapped[float] = mapped_column(Float, default=0.0)
    brier_score: Mapped[float] = mapped_column(Float, default=0.0)
    roc_auc: Mapped[float] = mapped_column(Float, default=0.0)

    train_size: Mapped[int] = mapped_column(Integer, default=0)
    test_size: Mapped[int] = mapped_column(Integer, default=0)

    selected: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    

class ProviderSyncLog(Base):
    __tablename__ = "provider_sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    provider: Mapped[str] = mapped_column(String(40), index=True)
    sync_type: Mapped[str] = mapped_column(String(80), index=True)

    status: Mapped[str] = mapped_column(String(40), default="started", index=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    records_received: Mapped[int] = mapped_column(Integer, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    records_skipped: Mapped[int] = mapped_column(Integer, default=0)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class OddsMarketMap(Base):
    __tablename__ = "odds_market_maps"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_market_name",
            "provider_selection_name",
            name="uq_odds_market_provider_mapping",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    provider: Mapped[str] = mapped_column(String(40), index=True)

    provider_market_name: Mapped[str] = mapped_column(String(160), index=True)
    provider_selection_name: Mapped[str] = mapped_column(String(160), index=True)

    internal_market: Mapped[str] = mapped_column(String(80), index=True)
    internal_selection: Mapped[str] = mapped_column(String(80), index=True)

    line_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True)  
