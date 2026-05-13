"""add_prediction_odds_source_traceability

Revision ID: 841a_prediction_odds_source
Revises: 840a_odds_ecosystem
Create Date: 2026-05-13 16:30:00.000000
"""

from alembic import op


revision = "841a_prediction_odds_source"
down_revision = "840a_odds_ecosystem"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS odds_bookmaker VARCHAR(120);
    """)

    op.execute("""
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS odds_market VARCHAR(160);
    """)

    op.execute("""
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS odds_selection VARCHAR(160);
    """)

    op.execute("""
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS odds_retrieved_at TIMESTAMP;
    """)

    op.execute("""
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS odds_match_quality VARCHAR(60);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_predictions_odds_bookmaker
        ON predictions (odds_bookmaker);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_predictions_odds_market
        ON predictions (odds_market);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_predictions_odds_selection
        ON predictions (odds_selection);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_predictions_odds_retrieved_at
        ON predictions (odds_retrieved_at);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_predictions_odds_match_quality
        ON predictions (odds_match_quality);
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS ix_predictions_odds_match_quality;
    """)

    op.execute("""
        DROP INDEX IF EXISTS ix_predictions_odds_retrieved_at;
    """)

    op.execute("""
        DROP INDEX IF EXISTS ix_predictions_odds_selection;
    """)

    op.execute("""
        DROP INDEX IF EXISTS ix_predictions_odds_market;
    """)

    op.execute("""
        DROP INDEX IF EXISTS ix_predictions_odds_bookmaker;
    """)

    op.execute("""
        ALTER TABLE predictions
        DROP COLUMN IF EXISTS odds_match_quality;
    """)

    op.execute("""
        ALTER TABLE predictions
        DROP COLUMN IF EXISTS odds_retrieved_at;
    """)

    op.execute("""
        ALTER TABLE predictions
        DROP COLUMN IF EXISTS odds_selection;
    """)

    op.execute("""
        ALTER TABLE predictions
        DROP COLUMN IF EXISTS odds_market;
    """)

    op.execute("""
        ALTER TABLE predictions
        DROP COLUMN IF EXISTS odds_bookmaker;
    """)