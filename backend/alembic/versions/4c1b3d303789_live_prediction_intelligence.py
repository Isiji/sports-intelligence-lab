# backend/alembic/versions/4c1b3d303789_live_prediction_intelligence.py

"""live_prediction_intelligence

Revision ID: 4c1b3d303789
Revises: d2904bb1275a
Create Date: 2026-05-11 12:19:25.377063
"""

from alembic import op


revision = "4c1b3d303789"
down_revision = "d2904bb1275a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS dynamic_league_tiers (
        id SERIAL PRIMARY KEY,
        league VARCHAR(160) NOT NULL UNIQUE,
        tier VARCHAR(40) NOT NULL,
        strength_score FLOAT NOT NULL DEFAULT 0,
        profitability_score FLOAT NOT NULL DEFAULT 0,
        stats_quality_score FLOAT NOT NULL DEFAULT 0,
        odds_quality_score FLOAT NOT NULL DEFAULT 0,
        survivability_score FLOAT NOT NULL DEFAULT 0,
        prediction_count INTEGER NOT NULL DEFAULT 0,
        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS ix_dynamic_league_tiers_league
    ON dynamic_league_tiers (league)
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_dynamic_league_tiers_tier
    ON dynamic_league_tiers (tier)
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS market_family_snapshots (
        id SERIAL PRIMARY KEY,
        family_name VARCHAR(80) NOT NULL UNIQUE,
        bets INTEGER NOT NULL DEFAULT 0,
        hit_rate FLOAT NOT NULL DEFAULT 0,
        roi FLOAT NOT NULL DEFAULT 0,
        survivability_score FLOAT NOT NULL DEFAULT 0,
        confidence_multiplier FLOAT NOT NULL DEFAULT 1,
        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_market_family_snapshots_family_name
    ON market_family_snapshots (family_name)
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS historical_backtest_bets (
        id SERIAL PRIMARY KEY,
        run_tag VARCHAR(120) NOT NULL,
        match_id INTEGER NOT NULL REFERENCES matches(id),
        league VARCHAR(160) NOT NULL,
        home_team VARCHAR(160) NOT NULL,
        away_team VARCHAR(160) NOT NULL,
        market VARCHAR(80) NOT NULL,
        predicted_label VARCHAR(80) NOT NULL,
        confidence FLOAT NOT NULL,
        odds FLOAT,
        implied_probability FLOAT,
        value_score FLOAT,
        won BOOLEAN NOT NULL,
        profit FLOAT NOT NULL,
        bankroll_after_bet FLOAT NOT NULL,
        stake FLOAT NOT NULL DEFAULT 100,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_historical_backtest_bet_unique
            UNIQUE (run_tag, market, match_id, predicted_label)
    )
    """)

    for index_name, column_name in [
        ("ix_historical_backtest_bets_run_tag", "run_tag"),
        ("ix_historical_backtest_bets_match_id", "match_id"),
        ("ix_historical_backtest_bets_league", "league"),
        ("ix_historical_backtest_bets_market", "market"),
        ("ix_historical_backtest_bets_predicted_label", "predicted_label"),
        ("ix_historical_backtest_bets_confidence", "confidence"),
        ("ix_historical_backtest_bets_odds", "odds"),
        ("ix_historical_backtest_bets_value_score", "value_score"),
        ("ix_historical_backtest_bets_won", "won"),
        ("ix_historical_backtest_bets_created_at", "created_at"),
    ]:
        op.execute(f"""
        CREATE INDEX IF NOT EXISTS {index_name}
        ON historical_backtest_bets ({column_name})
        """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS prediction_outcomes (
        id SERIAL PRIMARY KEY,
        prediction_id INTEGER NOT NULL REFERENCES predictions(id),
        match_id INTEGER NOT NULL REFERENCES matches(id),
        slate VARCHAR(120) NOT NULL,
        league VARCHAR(160) NOT NULL,
        market VARCHAR(80) NOT NULL,
        predicted_label VARCHAR(80) NOT NULL,
        confidence FLOAT NOT NULL,
        odds FLOAT,
        implied_probability FLOAT,
        value_score FLOAT,
        won BOOLEAN NOT NULL,
        profit FLOAT NOT NULL,
        settled_at TIMESTAMP NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS ix_prediction_outcomes_prediction_id
    ON prediction_outcomes (prediction_id)
    """)

    for index_name, column_name in [
        ("ix_prediction_outcomes_match_id", "match_id"),
        ("ix_prediction_outcomes_slate", "slate"),
        ("ix_prediction_outcomes_league", "league"),
        ("ix_prediction_outcomes_market", "market"),
        ("ix_prediction_outcomes_won", "won"),
        ("ix_prediction_outcomes_settled_at", "settled_at"),
    ]:
        op.execute(f"""
        CREATE INDEX IF NOT EXISTS {index_name}
        ON prediction_outcomes ({column_name})
        """)

    op.execute("""
    ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS is_correct BOOLEAN
    """)

    op.execute("""
    ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS result_label VARCHAR(80)
    """)

    op.execute("""
    ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS profit_loss FLOAT
    """)

    op.execute("""
    ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS stake FLOAT
    """)

    op.execute("""
    ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS settled_at TIMESTAMP
    """)

    op.execute("""
    ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS closing_odds FLOAT
    """)

    op.execute("""
    ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS clv FLOAT
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_predictions_is_correct
    ON predictions (is_correct)
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_predictions_result_label
    ON predictions (result_label)
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_predictions_settled_at
    ON predictions (settled_at)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_predictions_settled_at")
    op.execute("DROP INDEX IF EXISTS ix_predictions_result_label")
    op.execute("DROP INDEX IF EXISTS ix_predictions_is_correct")

    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS clv")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS closing_odds")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS settled_at")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS stake")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS profit_loss")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS result_label")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS is_correct")

    op.execute("DROP TABLE IF EXISTS prediction_outcomes")
    op.execute("DROP TABLE IF EXISTS historical_backtest_bets")
    op.execute("DROP TABLE IF EXISTS market_family_snapshots")
    op.execute("DROP TABLE IF EXISTS dynamic_league_tiers")