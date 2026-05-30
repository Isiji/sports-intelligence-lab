# backend/app/db/models.py

from datetime import date, datetime

from sqlalchemy import Boolean,Column,func, Date, JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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

    is_international: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_neutral_venue: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    tournament_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    tournament_stage: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    competition_priority: Mapped[float] = mapped_column(Float, default=0.0)
    tournament_pressure_score: Mapped[float] = mapped_column(Float, default=0.0)

    kickoff_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    is_finished: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_postponed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    has_stats: Mapped[bool] = mapped_column(Boolean, default=False)
    has_odds: Mapped[bool] = mapped_column(Boolean, default=False)
    is_valid_for_training: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    stats_attempted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    stats_attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    stats_unavailable: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    odds_attempted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    odds_attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    odds_unavailable: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
        
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


# backend/app/db/models.py
# REPLACE ONLY THE Prediction CLASS

class Prediction(Base):
    __tablename__ = "predictions"
    
    __table_args__ = (
            UniqueConstraint(
                "slate",
                "match_id",
                "market",
                "predicted_label",
                name="uq_prediction_unique_pick",
            ),
        )
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

    # =====================================================
    # ODDS SOURCE TRACEABILITY
    # =====================================================

    odds_bookmaker: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    odds_market: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
        index=True,
    )

    odds_selection: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
        index=True,
    )

    odds_retrieved_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
    )

    odds_match_quality: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
        index=True,
    )

    # =====================================================
    # PRODUCTION SETTLEMENT FIELDS
    # =====================================================

    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True, index=True)
    result_label: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    profit_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    stake: Mapped[float | None] = mapped_column(Float, nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    closing_odds: Mapped[float | None] = mapped_column(Float, nullable=True)
    clv: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
# backend/app/db/models.py
# ADD THESE FIELDS INSIDE Prediction CLASS

    # =====================================================
    # EXECUTION INTELLIGENCE
    # =====================================================

    execution_market: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    execution_selection: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    execution_family: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        index=True,
    )

    execution_line: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    bookmaker_locality: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        index=True,
    )

    local_realism_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    execution_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        index=True,
    )

    survivability_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        index=True,
    )

    execution_ready: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        index=True,
    )

    execution_reasons: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    market_alternatives: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )
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


# backend/app/db/models.py
# ADD THIS CLASS AT THE BOTTOM OF YOUR EXISTING FILE

class StatsQualitySnapshot(Base):
    __tablename__ = "stats_quality_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "sport",
            "competition_id",
            "season",
            name="uq_stats_quality_sport_league_season",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    sport: Mapped[str] = mapped_column(String(30), default="football", index=True)
    competition_id: Mapped[int | None] = mapped_column(
        ForeignKey("competitions.id"),
        nullable=True,
        index=True,
    )

    league: Mapped[str] = mapped_column(String(160), index=True)
    season: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    finished_matches: Mapped[int] = mapped_column(Integer, default=0)
    matches_with_stats: Mapped[int] = mapped_column(Integer, default=0)
    matches_with_real_stats: Mapped[int] = mapped_column(Integer, default=0)
    matches_with_odds: Mapped[int] = mapped_column(Integer, default=0)

    stat_rows: Mapped[int] = mapped_column(Integer, default=0)
    real_stat_rows: Mapped[int] = mapped_column(Integer, default=0)

    coverage_score: Mapped[float] = mapped_column(Float, default=0.0)
    realness_score: Mapped[float] = mapped_column(Float, default=0.0)
    odds_score: Mapped[float] = mapped_column(Float, default=0.0)
    sample_size_score: Mapped[float] = mapped_column(Float, default=0.0)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)

    quality_tier: Mapped[str] = mapped_column(String(40), default="poor", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    
    

class MarketReliabilitySnapshot(Base):
    __tablename__ = "market_reliability_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "sport",
            "market",
            name="uq_market_reliability_sport_market",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    sport: Mapped[str] = mapped_column(String(30), default="football", index=True)
    market: Mapped[str] = mapped_column(String(80), index=True)

    settled_predictions: Mapped[int] = mapped_column(Integer, default=0)
    correct_predictions: Mapped[int] = mapped_column(Integer, default=0)

    accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    avg_value_score: Mapped[float] = mapped_column(Float, default=0.0)

    reliability_score: Mapped[float] = mapped_column(Float, default=0.0)
    reliability_tier: Mapped[str] = mapped_column(String(40), default="poor", index=True)

    prediction_allowed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    confidence_multiplier: Mapped[float] = mapped_column(Float, default=0.5)

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    
    
class TeamRating(Base):
    __tablename__ = "team_ratings"
    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "sport",
            name="uq_team_rating_team_sport",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"),
        index=True,
    )

    sport: Mapped[str] = mapped_column(String(30), default="football", index=True)

    overall_elo: Mapped[float] = mapped_column(Float, default=1500.0)
    attack_elo: Mapped[float] = mapped_column(Float, default=1500.0)
    defense_elo: Mapped[float] = mapped_column(Float, default=1500.0)
    form_elo: Mapped[float] = mapped_column(Float, default=0.0)

    matches_played: Mapped[int] = mapped_column(Integer, default=0)

    wins: Mapped[int] = mapped_column(Integer, default=0)
    draws: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)

    goals_scored: Mapped[int] = mapped_column(Integer, default=0)
    goals_conceded: Mapped[int] = mapped_column(Integer, default=0)

    last_match_id: Mapped[int | None] = mapped_column(
        ForeignKey("matches.id"),
        nullable=True,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )
    
class FootballFeatureSnapshot(Base):
    __tablename__ = "football_feature_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "match_id",
            name="uq_feature_snapshot_match",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id"),
        index=True,
    )

    features_json: Mapped[dict] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class HistoricalBacktestBet(Base):
    __tablename__ = "historical_backtest_bets"
    __table_args__ = (
        UniqueConstraint(
            "run_tag",
            "market",
            "match_id",
            "predicted_label",
            name="uq_historical_backtest_bet_unique",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    run_tag: Mapped[str] = mapped_column(String(120), index=True)

    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)

    league: Mapped[str] = mapped_column(String(160), index=True)
    home_team: Mapped[str] = mapped_column(String(160))
    away_team: Mapped[str] = mapped_column(String(160))

    market: Mapped[str] = mapped_column(String(80), index=True)
    predicted_label: Mapped[str] = mapped_column(String(80), index=True)

    confidence: Mapped[float] = mapped_column(Float, index=True)
    odds: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    implied_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)

    won: Mapped[bool] = mapped_column(Boolean, index=True)
    profit: Mapped[float] = mapped_column(Float)
    bankroll_after_bet: Mapped[float] = mapped_column(Float)

    stake: Mapped[float] = mapped_column(Float, default=100.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


# =========================================================
# EXECUTION MARKET INTELLIGENCE
# =========================================================

class ExecutionMarketIntelligenceSnapshot(Base):
    __tablename__ = "execution_market_intelligence_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    sport: Mapped[str] = mapped_column(String(30), default="football", index=True)
    execution_market: Mapped[str] = mapped_column(String(120), unique=True, index=True)

    settled_predictions: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)

    hit_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_odds: Mapped[float] = mapped_column(Float, default=0.0)
    profit_loss: Mapped[float] = mapped_column(Float, default=0.0)
    roi: Mapped[float] = mapped_column(Float, default=0.0)

    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    survivability_score: Mapped[float] = mapped_column(Float, default=0.0)

    verdict: Mapped[str] = mapped_column(String(40), default="WATCHLIST", index=True)
    prediction_allowed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    grouping_allowed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    confidence_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )
    
# =========================================================
# ADVANCED INTELLIGENCE SNAPSHOTS
# =========================================================

class MarketIntelligenceSnapshot(Base):
    __tablename__ = "market_intelligence_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    sport: Mapped[str] = mapped_column(String(30), default="football", index=True)

    market: Mapped[str] = mapped_column(
        String(80),
        index=True,
    )

    bets: Mapped[int] = mapped_column(Integer, default=0)

    hit_rate: Mapped[float] = mapped_column(Float, default=0.0)
    roi: Mapped[float] = mapped_column(Float, default=0.0)

    avg_odds: Mapped[float] = mapped_column(Float, default=0.0)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    avg_value_score: Mapped[float] = mapped_column(Float, default=0.0)

    survivability_score: Mapped[float] = mapped_column(Float, default=0.0)

    recent_roi: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default="0",
    )

    recent_hit_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default="0",
    )

    decay_factor: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        server_default="1",
    )

    stale: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        index=True,
    )

    confidence_multiplier: Mapped[float] = mapped_column(Float, default=1.0)

    prediction_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
    )

    verdict: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class LeagueIntelligenceSnapshot(Base):
    __tablename__ = "league_intelligence_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    sport: Mapped[str] = mapped_column(String(30), default="football", index=True)

    competition_id: Mapped[int | None] = mapped_column(
        ForeignKey("competitions.id"),
        nullable=True,
        index=True,
    )

    league: Mapped[str] = mapped_column(String(160), index=True)

    season: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    bets: Mapped[int] = mapped_column(Integer, default=0)

    hit_rate: Mapped[float] = mapped_column(Float, default=0.0)
    roi: Mapped[float] = mapped_column(Float, default=0.0)

    avg_odds: Mapped[float] = mapped_column(Float, default=0.0)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    avg_value_score: Mapped[float] = mapped_column(Float, default=0.0)

    survivability_score: Mapped[float] = mapped_column(Float, default=0.0)

    recent_roi: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default="0",
    )

    recent_hit_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default="0",
    )

    decay_factor: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        server_default="1",
    )

    stale: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        index=True,
    )

    confidence_multiplier: Mapped[float] = mapped_column(Float, default=1.0)

    stats_quality_score: Mapped[float] = mapped_column(Float, default=0.0)

    safe_for_accumulators: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    prediction_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
    )

    verdict: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class LeagueMarketIntelligenceSnapshot(Base):
    __tablename__ = "league_market_intelligence_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    sport: Mapped[str] = mapped_column(String(30), default="football", index=True)

    competition_id: Mapped[int | None] = mapped_column(
        ForeignKey("competitions.id"),
        nullable=True,
        index=True,
    )

    league: Mapped[str] = mapped_column(String(160), index=True)

    season: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    market: Mapped[str] = mapped_column(String(80), index=True)

    bets: Mapped[int] = mapped_column(Integer, default=0)

    hit_rate: Mapped[float] = mapped_column(Float, default=0.0)
    roi: Mapped[float] = mapped_column(Float, default=0.0)

    avg_odds: Mapped[float] = mapped_column(Float, default=0.0)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    avg_value_score: Mapped[float] = mapped_column(Float, default=0.0)

    survivability_score: Mapped[float] = mapped_column(Float, default=0.0)

    recent_roi: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default="0",
    )

    recent_hit_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default="0",
    )

    decay_factor: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        server_default="1",
    )

    stale: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        index=True,
    )

    confidence_multiplier: Mapped[float] = mapped_column(Float, default=1.0)

    prediction_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
    )

    verdict: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

class OddsBandIntelligenceSnapshot(Base):
    __tablename__ = "odds_band_intelligence_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    market: Mapped[str] = mapped_column(String(80), index=True)

    odds_band: Mapped[str] = mapped_column(String(40), index=True)

    bets: Mapped[int] = mapped_column(Integer, default=0)

    hit_rate: Mapped[float] = mapped_column(Float, default=0.0)
    roi: Mapped[float] = mapped_column(Float, default=0.0)

    survivability_score: Mapped[float] = mapped_column(Float, default=0.0)

    confidence_multiplier: Mapped[float] = mapped_column(Float, default=1.0)

    prediction_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
    )

    verdict: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class ConfidenceBandIntelligenceSnapshot(Base):
    __tablename__ = "confidence_band_intelligence_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    market: Mapped[str] = mapped_column(String(80), index=True)

    confidence_band: Mapped[str] = mapped_column(String(40), index=True)

    bets: Mapped[int] = mapped_column(Integer, default=0)

    hit_rate: Mapped[float] = mapped_column(Float, default=0.0)
    roi: Mapped[float] = mapped_column(Float, default=0.0)

    survivability_score: Mapped[float] = mapped_column(Float, default=0.0)

    confidence_multiplier: Mapped[float] = mapped_column(Float, default=1.0)

    prediction_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
    )

    verdict: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    
# =========================================================
# LIVE PREDICTION OUTCOMES
# =========================================================

# backend/app/db/models.py
# REPLACE ONLY THE PredictionOutcome CLASS WITH THIS VERSION

class PredictionOutcome(Base):
    __tablename__ = "prediction_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("predictions.id"),
        index=True,
        unique=True,
    )

    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id"),
        index=True,
    )

    slate: Mapped[str] = mapped_column(String(120), index=True)

    league: Mapped[str] = mapped_column(String(160), index=True)

    market: Mapped[str] = mapped_column(String(80), index=True)

    predicted_label: Mapped[str] = mapped_column(String(80), index=True)

    result_label: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        index=True,
    )

    confidence: Mapped[float] = mapped_column(Float)

    odds: Mapped[float | None] = mapped_column(Float, nullable=True)

    closing_odds: Mapped[float | None] = mapped_column(Float, nullable=True)

    clv: Mapped[float | None] = mapped_column(Float, nullable=True)

    implied_probability: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    value_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    won: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        index=True,
    )

    profit: Mapped[float] = mapped_column(Float, default=0.0)

    stake: Mapped[float] = mapped_column(Float, default=100.0)

    settled_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True,
    )

# =========================================================
# DYNAMIC LEAGUE TIERS
# =========================================================

class DynamicLeagueTier(Base):
    __tablename__ = "dynamic_league_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    league: Mapped[str] = mapped_column(
        String(160),
        unique=True,
        index=True,
    )

    tier: Mapped[str] = mapped_column(
        String(40),
        default="WEAK",
        index=True,
    )

    strength_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    profitability_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    stats_quality_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    odds_quality_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    survivability_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    prediction_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


# =========================================================
# MARKET FAMILY INTELLIGENCE
# =========================================================

# =========================================================
# EXECUTABLE MARKET FAMILY INTELLIGENCE
# =========================================================

class ExecutableMarketFamilySnapshot(Base):
    __tablename__ = "executable_market_family_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    family_name: Mapped[str] = mapped_column(
        String(120),
        unique=True,
        index=True,
    )

    derivative_type: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        index=True,
    )

    scope: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        index=True,
    )

    execution_risk: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        index=True,
    )

    volatility_tier: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        index=True,
    )

    bets: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    hit_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    roi: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    survivability_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    bookmaker_richness_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    confidence_multiplier: Mapped[float] = mapped_column(
        Float,
        default=1.0,
    )

    production_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


# =========================================================
# BOOKMAKER FAMILY INTELLIGENCE
# =========================================================

class BookmakerFamilyIntelligenceSnapshot(Base):
    __tablename__ = "bookmaker_family_intelligence_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    bookmaker: Mapped[str] = mapped_column(
        String(120),
        index=True,
    )

    family_name: Mapped[str] = mapped_column(
        String(120),
        index=True,
    )

    bets: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    hit_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    roi: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    sharpness_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    confidence_multiplier: Mapped[float] = mapped_column(
        Float,
        default=1.0,
    )

    bookmaker_tier: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
class MarketFamilySnapshot(Base):
    __tablename__ = "market_family_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    family_name: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        index=True,
    )

    bets: Mapped[int] = mapped_column(Integer, default=0)

    hit_rate: Mapped[float] = mapped_column(Float, default=0.0)

    roi: Mapped[float] = mapped_column(Float, default=0.0)

    survivability_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    confidence_multiplier: Mapped[float] = mapped_column(
        Float,
        default=1.0,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    
# =========================================================
# BOOKMAKER INTELLIGENCE
# =========================================================

class BookmakerIntelligenceSnapshot(Base):
    __tablename__ = "bookmaker_intelligence_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    bookmaker: Mapped[str] = mapped_column(
        String(120),
        unique=True,
        index=True,
    )

    bets: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    hit_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    roi: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    avg_odds: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    survivability_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    sharpness_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    bookmaker_tier: Mapped[str] = mapped_column(
        String(40),
        default="UNKNOWN",
        index=True,
    )

    confidence_multiplier: Mapped[float] = mapped_column(
        Float,
        default=1.0,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    
# backend/app/db/models.py
# ADD THIS CLASS NEAR OTHER INTELLIGENCE SNAPSHOTS

class LeagueOddsCoverageSnapshot(Base):
    __tablename__ = "league_odds_coverage_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "sport",
            "league",
            name="uq_league_odds_coverage_sport_league",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    sport: Mapped[str] = mapped_column(String(30), default="football", index=True)
    league: Mapped[str] = mapped_column(String(160), index=True)

    total_matches: Mapped[int] = mapped_column(Integer, default=0)
    matches_with_odds: Mapped[int] = mapped_column(Integer, default=0)
    odds_unavailable_matches: Mapped[int] = mapped_column(Integer, default=0)
    odds_attempted_matches: Mapped[int] = mapped_column(Integer, default=0)

    odds_coverage_rate: Mapped[float] = mapped_column(Float, default=0.0)
    odds_unavailable_rate: Mapped[float] = mapped_column(Float, default=0.0)

    total_odds_rows: Mapped[int] = mapped_column(Integer, default=0)
    avg_odds_rows_per_match: Mapped[float] = mapped_column(Float, default=0.0)

    supported_market_count: Mapped[int] = mapped_column(Integer, default=0)
    bookmaker_count: Mapped[int] = mapped_column(Integer, default=0)

    coverage_score: Mapped[float] = mapped_column(Float, default=0.0)
    coverage_tier: Mapped[str] = mapped_column(String(40), default="UNKNOWN", index=True)
# backend/app/db/models.py

    market_depth_score = Column(
        Float,
        default=0,
    )

    bookmaker_depth_score = Column(
        Float,
        default=0,
    )

    ecosystem_score = Column(
        Float,
        default=0,
    )

    priority_tier = Column(
        String(80),
        nullable=True,
        index=True,
    )

    last_odds_activity_at = Column(
        DateTime,
        nullable=True,
    )

    production_allowed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )
    
# backend/app/db/models.py
# ADD NEAR OTHER INTELLIGENCE SNAPSHOTS

class LeagueMarketCoverageSnapshot(Base):
    __tablename__ = "league_market_coverage_snapshots"

    __table_args__ = (
        UniqueConstraint(
            "sport",
            "league",
            "market",
            name="uq_league_market_coverage",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    sport: Mapped[str] = mapped_column(
        String(30),
        default="football",
        index=True,
    )

    league: Mapped[str] = mapped_column(
        String(160),
        index=True,
    )

    market: Mapped[str] = mapped_column(
        String(120),
        index=True,
    )

    matches_with_market: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    total_market_rows: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    bookmaker_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    market_coverage_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    avg_rows_per_match: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    market_quality_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )

    market_tier: Mapped[str] = mapped_column(
        String(40),
        default="UNKNOWN",
        index=True,
    )

    production_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )

class AutomationJob(Base):
    __tablename__ = "automation_jobs"

    id = Column(Integer, primary_key=True)

    job_key = Column(String(120), unique=True, index=True)

    enabled = Column(Boolean, default=True)

    cron_expression = Column(String(120))

    next_run_at = Column(DateTime)

    last_run_at = Column(DateTime)

    last_status = Column(String(40))

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )


class AutomationJobRun(Base):
    __tablename__ = "automation_job_runs"

    id = Column(Integer, primary_key=True)

    job_key = Column(
        String(120),
        index=True,
    )

    started_at = Column(DateTime)

    finished_at = Column(DateTime)

    status = Column(
        String(40),
        default="running",
    )

    duration_seconds = Column(Float)

    command_count = Column(Integer)

    output = Column(Text)

    error = Column(Text)