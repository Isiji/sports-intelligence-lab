# backend/app/db/models.py

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


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


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    slate: Mapped[str] = mapped_column(String(100), index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)

    sport: Mapped[str] = mapped_column(String(30), default="football", index=True)
    model_name: Mapped[str] = mapped_column(String(80), default="football_baseline_v1")
    market: Mapped[str] = mapped_column(String(60), default="home_win")

    predicted_label: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[float] = mapped_column(Float)

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