"""add_team_ratings

Revision ID: f76ac4b8ea1b
Revises: 0006_market_reliability
Create Date: 2026-05-07 13:05:52.977435
"""

from alembic import op
import sqlalchemy as sa


revision = "f76ac4b8ea1b"
down_revision = "0006_market_reliability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team_ratings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("sport", sa.String(length=30), nullable=False),
        sa.Column("overall_elo", sa.Float(), nullable=False),
        sa.Column("attack_elo", sa.Float(), nullable=False),
        sa.Column("defense_elo", sa.Float(), nullable=False),
        sa.Column("form_elo", sa.Float(), nullable=False),
        sa.Column("matches_played", sa.Integer(), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=False),
        sa.Column("draws", sa.Integer(), nullable=False),
        sa.Column("losses", sa.Integer(), nullable=False),
        sa.Column("goals_scored", sa.Integer(), nullable=False),
        sa.Column("goals_conceded", sa.Integer(), nullable=False),
        sa.Column("last_match_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["last_match_id"], ["matches.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "sport", name="uq_team_rating_team_sport"),
    )

    op.create_index("ix_team_ratings_last_match_id", "team_ratings", ["last_match_id"], unique=False)
    op.create_index("ix_team_ratings_sport", "team_ratings", ["sport"], unique=False)
    op.create_index("ix_team_ratings_team_id", "team_ratings", ["team_id"], unique=False)
    op.create_index("ix_team_ratings_updated_at", "team_ratings", ["updated_at"], unique=False)

    # Safe handling because some databases may not have this old index.
    op.execute("DROP INDEX IF EXISTS ix_stats_quality_snapshots_overall_score")

    # Safe handling because older DBs may have different constraint names.
    op.execute(
        """
        ALTER TABLE stats_quality_snapshots
        DROP CONSTRAINT IF EXISTS uq_stats_quality_sport_competition_season
        """
    )

    op.execute(
        """
        ALTER TABLE stats_quality_snapshots
        DROP CONSTRAINT IF EXISTS uq_stats_quality_sport_league_season
        """
    )

    op.create_unique_constraint(
        "uq_stats_quality_sport_league_season",
        "stats_quality_snapshots",
        ["sport", "competition_id", "season"],
    )

    # NOTE:
    # These team_match_stats changes were removed because this DB did not yet
    # have source/is_real/raw_stats_json/updated_at in the expected migration order.
    # They are already represented in the SQLAlchemy model and should be handled
    # by a separate safe migration if needed.


def downgrade() -> None:
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

    op.drop_index("ix_team_ratings_updated_at", table_name="team_ratings")
    op.drop_index("ix_team_ratings_team_id", table_name="team_ratings")
    op.drop_index("ix_team_ratings_sport", table_name="team_ratings")
    op.drop_index("ix_team_ratings_last_match_id", table_name="team_ratings")
    op.drop_table("team_ratings")