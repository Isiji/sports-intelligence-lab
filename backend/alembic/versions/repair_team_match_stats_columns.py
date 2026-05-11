"""repair team_match_stats missing columns

Revision ID: repair_team_match_stats_columns
Revises: add_ingestion_attempt_tracking
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa


revision = "repair_team_match_stats_columns"
down_revision = "add_ingestion_attempt_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE team_match_stats
        ADD COLUMN IF NOT EXISTS source VARCHAR(40)
        """
    )

    op.execute(
        """
        ALTER TABLE team_match_stats
        ADD COLUMN IF NOT EXISTS is_real BOOLEAN DEFAULT FALSE
        """
    )

    op.execute(
        """
        ALTER TABLE team_match_stats
        ADD COLUMN IF NOT EXISTS raw_stats_json JSON
        """
    )

    op.execute(
        """
        ALTER TABLE team_match_stats
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP
        """
    )

    op.execute(
        """
        UPDATE team_match_stats
        SET source = 'placeholder'
        WHERE source IS NULL
        """
    )

    op.execute(
        """
        UPDATE team_match_stats
        SET is_real = FALSE
        WHERE is_real IS NULL
        """
    )

    op.execute(
        """
        UPDATE team_match_stats
        SET updated_at = NOW()
        WHERE updated_at IS NULL
        """
    )

    op.alter_column(
        "team_match_stats",
        "source",
        nullable=False,
    )

    op.alter_column(
        "team_match_stats",
        "is_real",
        nullable=False,
    )

    op.alter_column(
        "team_match_stats",
        "updated_at",
        nullable=False,
    )



def downgrade() -> None:
    op.drop_index("ix_team_match_stats_is_real", table_name="team_match_stats")
    op.drop_index("ix_team_match_stats_source", table_name="team_match_stats")

    op.drop_column("team_match_stats", "updated_at")
    op.drop_column("team_match_stats", "raw_stats_json")
    op.drop_column("team_match_stats", "is_real")
    op.drop_column("team_match_stats", "source")