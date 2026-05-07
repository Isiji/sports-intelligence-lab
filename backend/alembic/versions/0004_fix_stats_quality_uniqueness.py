# backend/alembic/versions/0004_stats_fix.py

"""fix stats quality uniqueness

Revision ID: 0004_stats_fix
Revises: 0003_stats_quality_scoring
Create Date: 2026-05-07
"""

from alembic import op


revision = "0004_stats_fix"
down_revision = "0003_stats_quality_scoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_stats_quality_sport_league_season",
        "stats_quality_snapshots",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_stats_quality_sport_competition_season",
        "stats_quality_snapshots",
        ["sport", "competition_id", "season"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_stats_quality_sport_competition_season",
        "stats_quality_snapshots",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_stats_quality_sport_league_season",
        "stats_quality_snapshots",
        ["sport", "league", "season"],
    )