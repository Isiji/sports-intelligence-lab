# backend/alembic/versions/839a_fix_manual_schema_reconciliation.py

"""fix_manual_schema_reconciliation

Revision ID: 839a_manual_schema_fix
Revises: 838f42a7d1aa
Create Date: 2026-05-11 19:10:00.000000
"""

from alembic import op


revision = "839a_manual_schema_fix"
down_revision = "838f42a7d1aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS is_correct BOOLEAN;
    """)

    op.execute("""
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS result_label VARCHAR(80);
    """)

    op.execute("""
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS profit_loss FLOAT;
    """)

    op.execute("""
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS stake FLOAT;
    """)

    op.execute("""
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS settled_at TIMESTAMP;
    """)

    op.execute("""
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS closing_odds FLOAT;
    """)

    op.execute("""
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS clv FLOAT;
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS dynamic_league_tiers (
            id SERIAL PRIMARY KEY,
            league VARCHAR(160) UNIQUE NOT NULL,
            tier VARCHAR(40) NOT NULL,
            strength_score FLOAT DEFAULT 0,
            profitability_score FLOAT DEFAULT 0,
            stats_quality_score FLOAT DEFAULT 0,
            odds_quality_score FLOAT DEFAULT 0,
            survivability_score FLOAT DEFAULT 0,
            prediction_count INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_dynamic_league_tiers_league
        ON dynamic_league_tiers (league);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_dynamic_league_tiers_tier
        ON dynamic_league_tiers (tier);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_dynamic_league_tiers_tier;")
    op.execute("DROP INDEX IF EXISTS ix_dynamic_league_tiers_league;")
    op.execute("DROP TABLE IF EXISTS dynamic_league_tiers;")

    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS clv;")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS closing_odds;")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS settled_at;")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS stake;")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS profit_loss;")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS result_label;")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS is_correct;")