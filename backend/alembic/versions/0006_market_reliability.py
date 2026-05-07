# backend/alembic/versions/0006_market_reliability.py

"""add market reliability snapshots

Revision ID: 0006_market_reliability
Revises: 0005_league_intel
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_market_reliability"
down_revision = "0005_league_intel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_reliability_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sport", sa.String(length=30), nullable=False, server_default="football"),
        sa.Column("market", sa.String(length=80), nullable=False),
        sa.Column("settled_predictions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct_predictions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accuracy", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_value_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reliability_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reliability_tier", sa.String(length=40), nullable=False, server_default="poor"),
        sa.Column("prediction_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("confidence_multiplier", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "sport",
            "market",
            name="uq_market_reliability_sport_market",
        ),
    )

    op.create_index("ix_market_reliability_snapshots_sport", "market_reliability_snapshots", ["sport"])
    op.create_index("ix_market_reliability_snapshots_market", "market_reliability_snapshots", ["market"])
    op.create_index("ix_market_reliability_snapshots_reliability_tier", "market_reliability_snapshots", ["reliability_tier"])
    op.create_index("ix_market_reliability_snapshots_prediction_allowed", "market_reliability_snapshots", ["prediction_allowed"])


def downgrade() -> None:
    op.drop_index("ix_market_reliability_snapshots_prediction_allowed", table_name="market_reliability_snapshots")
    op.drop_index("ix_market_reliability_snapshots_reliability_tier", table_name="market_reliability_snapshots")
    op.drop_index("ix_market_reliability_snapshots_market", table_name="market_reliability_snapshots")
    op.drop_index("ix_market_reliability_snapshots_sport", table_name="market_reliability_snapshots")
    op.drop_table("market_reliability_snapshots")