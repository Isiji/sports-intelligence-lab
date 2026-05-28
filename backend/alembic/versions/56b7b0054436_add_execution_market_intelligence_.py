"""add execution market intelligence snapshots

Revision ID: 845a_execution_market_intelligence
Revises: 844a_bookmaker_execution_fields
Create Date: 2026-05-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "845a_execution_market_intelligence"
down_revision = "844a_bookmaker_execution_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =====================================================
    # SYNC MANUAL DB FIXES INTO ALEMBIC HISTORY
    # =====================================================

    op.execute(
        "ALTER TABLE prediction_outcomes "
        "ADD COLUMN IF NOT EXISTS result_label VARCHAR(80)"
    )

    op.execute(
        "ALTER TABLE prediction_outcomes "
        "ADD COLUMN IF NOT EXISTS closing_odds DOUBLE PRECISION"
    )

    op.execute(
        "ALTER TABLE prediction_outcomes "
        "ADD COLUMN IF NOT EXISTS clv DOUBLE PRECISION"
    )

    op.execute(
        "ALTER TABLE prediction_outcomes "
        "ADD COLUMN IF NOT EXISTS implied_probability DOUBLE PRECISION"
    )

    op.execute(
        "ALTER TABLE prediction_outcomes "
        "ADD COLUMN IF NOT EXISTS value_score DOUBLE PRECISION"
    )

    op.execute(
        "ALTER TABLE prediction_outcomes "
        "ADD COLUMN IF NOT EXISTS stake DOUBLE PRECISION DEFAULT 100.0"
    )

    op.execute(
        "ALTER TABLE prediction_outcomes "
        "ADD COLUMN IF NOT EXISTS settled_at TIMESTAMP"
    )

    # =====================================================
    # EXECUTION MARKET INTELLIGENCE SNAPSHOTS
    # =====================================================

    op.create_table(
        "execution_market_intelligence_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sport", sa.String(length=30), nullable=False, server_default="football"),
        sa.Column("execution_market", sa.String(length=120), nullable=False),
        sa.Column("settled_predictions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hit_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_odds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("profit_loss", sa.Float(), nullable=False, server_default="0"),
        sa.Column("roi", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("survivability_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("verdict", sa.String(length=40), nullable=False, server_default="WATCHLIST"),
        sa.Column("prediction_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("grouping_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("confidence_multiplier", sa.Float(), nullable=False, server_default="1"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "execution_market",
            name="uq_execution_market_intelligence_market",
        ),
    )

    op.create_index(
        "ix_execution_market_intelligence_snapshots_sport",
        "execution_market_intelligence_snapshots",
        ["sport"],
    )

    op.create_index(
        "ix_execution_market_intelligence_snapshots_execution_market",
        "execution_market_intelligence_snapshots",
        ["execution_market"],
    )

    op.create_index(
        "ix_execution_market_intelligence_snapshots_verdict",
        "execution_market_intelligence_snapshots",
        ["verdict"],
    )

    op.create_index(
        "ix_execution_market_intelligence_snapshots_prediction_allowed",
        "execution_market_intelligence_snapshots",
        ["prediction_allowed"],
    )

    op.create_index(
        "ix_execution_market_intelligence_snapshots_grouping_allowed",
        "execution_market_intelligence_snapshots",
        ["grouping_allowed"],
    )


def downgrade() -> None:
    op.drop_table("execution_market_intelligence_snapshots")