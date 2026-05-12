# backend/alembic/versions/838f42a7d1aa_add_league_market_coverage_snapshots.py

"""add_league_market_coverage_snapshots

Revision ID: 838f42a7d1aa
Revises: 837c9d2e91aa
Create Date: 2026-05-11 18:30:00.000000
"""

from alembic import op


revision = "838f42a7d1aa"
down_revision = "837c9d2e91aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS league_market_coverage_snapshots (
        id SERIAL PRIMARY KEY,

        sport VARCHAR(30) NOT NULL,

        league VARCHAR(160) NOT NULL,

        market VARCHAR(120) NOT NULL,

        matches_with_market INTEGER NOT NULL DEFAULT 0,

        total_market_rows INTEGER NOT NULL DEFAULT 0,

        bookmaker_count INTEGER NOT NULL DEFAULT 0,

        market_coverage_rate FLOAT NOT NULL DEFAULT 0,

        avg_rows_per_match FLOAT NOT NULL DEFAULT 0,

        market_quality_score FLOAT NOT NULL DEFAULT 0,

        market_tier VARCHAR(40) NOT NULL,

        production_allowed BOOLEAN NOT NULL DEFAULT FALSE,

        reason TEXT,

        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

        CONSTRAINT uq_league_market_coverage
            UNIQUE (sport, league, market)
    )
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_league_market_coverage_snapshots_sport
    ON league_market_coverage_snapshots (sport)
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_league_market_coverage_snapshots_league
    ON league_market_coverage_snapshots (league)
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_league_market_coverage_snapshots_market
    ON league_market_coverage_snapshots (market)
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_league_market_coverage_snapshots_market_tier
    ON league_market_coverage_snapshots (market_tier)
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_league_market_coverage_snapshots_production_allowed
    ON league_market_coverage_snapshots (production_allowed)
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS league_market_coverage_snapshots
    """)