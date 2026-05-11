# backend/alembic/versions/837c9d2e91aa_add_league_odds_coverage_snapshots.py

"""add_league_odds_coverage_snapshots

Revision ID: 837c9d2e91aa
Revises: 836b71c7f1c4
Create Date: 2026-05-11 17:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "837c9d2e91aa"
down_revision = "836b71c7f1c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "league_odds_coverage_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sport", sa.String(length=30), nullable=False),
        sa.Column("league", sa.String(length=160), nullable=False),
        sa.Column("total_matches", sa.Integer(), nullable=False),
        sa.Column("matches_with_odds", sa.Integer(), nullable=False),
        sa.Column("odds_unavailable_matches", sa.Integer(), nullable=False),
        sa.Column("odds_attempted_matches", sa.Integer(), nullable=False),
        sa.Column("odds_coverage_rate", sa.Float(), nullable=False),
        sa.Column("odds_unavailable_rate", sa.Float(), nullable=False),
        sa.Column("total_odds_rows", sa.Integer(), nullable=False),
        sa.Column("avg_odds_rows_per_match", sa.Float(), nullable=False),
        sa.Column("supported_market_count", sa.Integer(), nullable=False),
        sa.Column("bookmaker_count", sa.Integer(), nullable=False),
        sa.Column("coverage_score", sa.Float(), nullable=False),
        sa.Column("coverage_tier", sa.String(length=40), nullable=False),
        sa.Column("production_allowed", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "sport",
            "league",
            name="uq_league_odds_coverage_sport_league",
        ),
    )

    op.create_index(
        op.f("ix_league_odds_coverage_snapshots_sport"),
        "league_odds_coverage_snapshots",
        ["sport"],
        unique=False,
    )
    op.create_index(
        op.f("ix_league_odds_coverage_snapshots_league"),
        "league_odds_coverage_snapshots",
        ["league"],
        unique=False,
    )
    op.create_index(
        op.f("ix_league_odds_coverage_snapshots_coverage_tier"),
        "league_odds_coverage_snapshots",
        ["coverage_tier"],
        unique=False,
    )
    op.create_index(
        op.f("ix_league_odds_coverage_snapshots_production_allowed"),
        "league_odds_coverage_snapshots",
        ["production_allowed"],
        unique=False,
    )
    op.create_index(
        op.f("ix_league_odds_coverage_snapshots_updated_at"),
        "league_odds_coverage_snapshots",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_league_odds_coverage_snapshots_updated_at"),
        table_name="league_odds_coverage_snapshots",
    )
    op.drop_index(
        op.f("ix_league_odds_coverage_snapshots_production_allowed"),
        table_name="league_odds_coverage_snapshots",
    )
    op.drop_index(
        op.f("ix_league_odds_coverage_snapshots_coverage_tier"),
        table_name="league_odds_coverage_snapshots",
    )
    op.drop_index(
        op.f("ix_league_odds_coverage_snapshots_league"),
        table_name="league_odds_coverage_snapshots",
    )
    op.drop_index(
        op.f("ix_league_odds_coverage_snapshots_sport"),
        table_name="league_odds_coverage_snapshots",
    )
    op.drop_table("league_odds_coverage_snapshots")