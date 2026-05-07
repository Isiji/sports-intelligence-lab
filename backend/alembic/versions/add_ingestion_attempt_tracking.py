# backend/alembic/versions/add_ingestion_attempt_tracking.py

"""add ingestion attempt tracking

Revision ID: add_ingestion_attempt_tracking
Revises: b46dd2830c1e
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa


revision = "add_ingestion_attempt_tracking"
down_revision = "b46dd2830c1e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("stats_attempted_at", sa.DateTime(), nullable=True))
    op.add_column("matches", sa.Column("stats_attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("matches", sa.Column("stats_unavailable", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.add_column("matches", sa.Column("odds_attempted_at", sa.DateTime(), nullable=True))
    op.add_column("matches", sa.Column("odds_attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("matches", sa.Column("odds_unavailable", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_index("ix_matches_stats_attempted_at", "matches", ["stats_attempted_at"])
    op.create_index("ix_matches_stats_unavailable", "matches", ["stats_unavailable"])
    op.create_index("ix_matches_odds_attempted_at", "matches", ["odds_attempted_at"])
    op.create_index("ix_matches_odds_unavailable", "matches", ["odds_unavailable"])


def downgrade() -> None:
    op.drop_index("ix_matches_odds_unavailable", table_name="matches")
    op.drop_index("ix_matches_odds_attempted_at", table_name="matches")
    op.drop_index("ix_matches_stats_unavailable", table_name="matches")
    op.drop_index("ix_matches_stats_attempted_at", table_name="matches")

    op.drop_column("matches", "odds_unavailable")
    op.drop_column("matches", "odds_attempt_count")
    op.drop_column("matches", "odds_attempted_at")

    op.drop_column("matches", "stats_unavailable")
    op.drop_column("matches", "stats_attempt_count")
    op.drop_column("matches", "stats_attempted_at")