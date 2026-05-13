# backend/alembic/versions/840a_add_league_odds_ecosystem_scoring.py

"""add_league_odds_ecosystem_scoring

Revision ID: 840a_add_league_odds_ecosystem_scoring
Revises: 839a_manual_schema_fix
Create Date: 2026-05-13 13:30:00.000000
"""

from alembic import op


revision = "840a_odds_ecosystem"
down_revision = "839a_manual_schema_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE league_odds_coverage_snapshots
        ADD COLUMN IF NOT EXISTS market_depth_score FLOAT DEFAULT 0;
    """)

    op.execute("""
        ALTER TABLE league_odds_coverage_snapshots
        ADD COLUMN IF NOT EXISTS bookmaker_depth_score FLOAT DEFAULT 0;
    """)

    op.execute("""
        ALTER TABLE league_odds_coverage_snapshots
        ADD COLUMN IF NOT EXISTS ecosystem_score FLOAT DEFAULT 0;
    """)

    op.execute("""
        ALTER TABLE league_odds_coverage_snapshots
        ADD COLUMN IF NOT EXISTS priority_tier VARCHAR(80);
    """)

    op.execute("""
        ALTER TABLE league_odds_coverage_snapshots
        ADD COLUMN IF NOT EXISTS last_odds_activity_at TIMESTAMP;
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS
        ix_league_odds_coverage_snapshots_priority_tier
        ON league_odds_coverage_snapshots (priority_tier);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS
        ix_league_odds_coverage_snapshots_ecosystem_score
        ON league_odds_coverage_snapshots (ecosystem_score);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS
        ix_league_odds_coverage_snapshots_production_allowed
        ON league_odds_coverage_snapshots (production_allowed);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS
        ix_league_odds_coverage_snapshots_coverage_tier
        ON league_odds_coverage_snapshots (coverage_tier);
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS
        ix_league_odds_coverage_snapshots_coverage_tier;
    """)

    op.execute("""
        DROP INDEX IF EXISTS
        ix_league_odds_coverage_snapshots_production_allowed;
    """)

    op.execute("""
        DROP INDEX IF EXISTS
        ix_league_odds_coverage_snapshots_ecosystem_score;
    """)

    op.execute("""
        DROP INDEX IF EXISTS
        ix_league_odds_coverage_snapshots_priority_tier;
    """)

    op.execute("""
        ALTER TABLE league_odds_coverage_snapshots
        DROP COLUMN IF EXISTS last_odds_activity_at;
    """)

    op.execute("""
        ALTER TABLE league_odds_coverage_snapshots
        DROP COLUMN IF EXISTS priority_tier;
    """)

    op.execute("""
        ALTER TABLE league_odds_coverage_snapshots
        DROP COLUMN IF EXISTS ecosystem_score;
    """)

    op.execute("""
        ALTER TABLE league_odds_coverage_snapshots
        DROP COLUMN IF EXISTS bookmaker_depth_score;
    """)

    op.execute("""
        ALTER TABLE league_odds_coverage_snapshots
        DROP COLUMN IF EXISTS market_depth_score;
    """)