# backend/alembic/versions/0003_stats_quality_scoring.py

"""add stats quality scoring

Revision ID: 0003_stats_quality_scoring
Revises: 0002_real_ingestion_foundation
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_stats_quality_scoring"
down_revision = "0002_real_ingestion_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stats_quality_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sport", sa.String(length=30), nullable=False, server_default="football"),
        sa.Column("competition_id", sa.Integer(), sa.ForeignKey("competitions.id"), nullable=True),
        sa.Column("league", sa.String(length=160), nullable=False),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("finished_matches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matches_with_stats", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matches_with_real_stats", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matches_with_odds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stat_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("real_stat_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("coverage_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("realness_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("odds_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sample_size_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("overall_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("quality_tier", sa.String(length=40), nullable=False, server_default="poor"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "sport",
            "league",
            "season",
            name="uq_stats_quality_sport_league_season",
        ),
    )

    op.create_index("ix_stats_quality_snapshots_sport", "stats_quality_snapshots", ["sport"])
    op.create_index("ix_stats_quality_snapshots_competition_id", "stats_quality_snapshots", ["competition_id"])
    op.create_index("ix_stats_quality_snapshots_league", "stats_quality_snapshots", ["league"])
    op.create_index("ix_stats_quality_snapshots_season", "stats_quality_snapshots", ["season"])
    op.create_index("ix_stats_quality_snapshots_quality_tier", "stats_quality_snapshots", ["quality_tier"])
    op.create_index("ix_stats_quality_snapshots_overall_score", "stats_quality_snapshots", ["overall_score"])


def downgrade() -> None:
    op.drop_index("ix_stats_quality_snapshots_overall_score", table_name="stats_quality_snapshots")
    op.drop_index("ix_stats_quality_snapshots_quality_tier", table_name="stats_quality_snapshots")
    op.drop_index("ix_stats_quality_snapshots_season", table_name="stats_quality_snapshots")
    op.drop_index("ix_stats_quality_snapshots_league", table_name="stats_quality_snapshots")
    op.drop_index("ix_stats_quality_snapshots_competition_id", table_name="stats_quality_snapshots")
    op.drop_index("ix_stats_quality_snapshots_sport", table_name="stats_quality_snapshots")
    op.drop_table("stats_quality_snapshots")