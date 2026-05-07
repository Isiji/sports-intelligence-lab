# backend/alembic/versions/0005_league_intel.py

"""add league intelligence snapshots

Revision ID: 0005_league_intel
Revises: 0004_stats_fix
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_league_intel"
down_revision = "0004_stats_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "league_intelligence_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sport", sa.String(length=30), nullable=False, server_default="football"),
        sa.Column("competition_id", sa.Integer(), sa.ForeignKey("competitions.id"), nullable=True),
        sa.Column("league", sa.String(length=160), nullable=False),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("stats_quality_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("data_tier", sa.String(length=40), nullable=False, server_default="poor"),
        sa.Column("prediction_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("training_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("confidence_multiplier", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("risk_level", sa.String(length=40), nullable=False, server_default="high"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "sport",
            "competition_id",
            "season",
            name="uq_league_intel_sport_competition_season",
        ),
    )

    op.create_index("ix_league_intelligence_snapshots_sport", "league_intelligence_snapshots", ["sport"])
    op.create_index("ix_league_intelligence_snapshots_competition_id", "league_intelligence_snapshots", ["competition_id"])
    op.create_index("ix_league_intelligence_snapshots_league", "league_intelligence_snapshots", ["league"])
    op.create_index("ix_league_intelligence_snapshots_season", "league_intelligence_snapshots", ["season"])
    op.create_index("ix_league_intelligence_snapshots_data_tier", "league_intelligence_snapshots", ["data_tier"])
    op.create_index("ix_league_intelligence_snapshots_prediction_allowed", "league_intelligence_snapshots", ["prediction_allowed"])
    op.create_index("ix_league_intelligence_snapshots_training_allowed", "league_intelligence_snapshots", ["training_allowed"])
    op.create_index("ix_league_intelligence_snapshots_risk_level", "league_intelligence_snapshots", ["risk_level"])


def downgrade() -> None:
    op.drop_index("ix_league_intelligence_snapshots_risk_level", table_name="league_intelligence_snapshots")
    op.drop_index("ix_league_intelligence_snapshots_training_allowed", table_name="league_intelligence_snapshots")
    op.drop_index("ix_league_intelligence_snapshots_prediction_allowed", table_name="league_intelligence_snapshots")
    op.drop_index("ix_league_intelligence_snapshots_data_tier", table_name="league_intelligence_snapshots")
    op.drop_index("ix_league_intelligence_snapshots_season", table_name="league_intelligence_snapshots")
    op.drop_index("ix_league_intelligence_snapshots_league", table_name="league_intelligence_snapshots")
    op.drop_index("ix_league_intelligence_snapshots_competition_id", table_name="league_intelligence_snapshots")
    op.drop_index("ix_league_intelligence_snapshots_sport", table_name="league_intelligence_snapshots")
    op.drop_table("league_intelligence_snapshots")