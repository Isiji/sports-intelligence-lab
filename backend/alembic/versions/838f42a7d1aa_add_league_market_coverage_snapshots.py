# backend/alembic/versions/838f42a7d1aa_add_league_market_coverage_snapshots.py

"""add_league_market_coverage_snapshots

Revision ID: 838f42a7d1aa
Revises: 837c9d2e91aa
Create Date: 2026-05-11 18:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "838f42a7d1aa"
down_revision = "837c9d2e91aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "league_market_coverage_snapshots",

        sa.Column("id", sa.Integer(), nullable=False),

        sa.Column("sport", sa.String(length=30), nullable=False),

        sa.Column("league", sa.String(length=160), nullable=False),

        sa.Column("market", sa.String(length=120), nullable=False),

        sa.Column("matches_with_market", sa.Integer(), nullable=False),

        sa.Column("total_market_rows", sa.Integer(), nullable=False),

        sa.Column("bookmaker_count", sa.Integer(), nullable=False),

        sa.Column("market_coverage_rate", sa.Float(), nullable=False),

        sa.Column("avg_rows_per_match", sa.Float(), nullable=False),

        sa.Column("market_quality_score", sa.Float(), nullable=False),

        sa.Column("market_tier", sa.String(length=40), nullable=False),

        sa.Column("production_allowed", sa.Boolean(), nullable=False),

        sa.Column("reason", sa.Text(), nullable=True),

        sa.Column("updated_at", sa.DateTime(), nullable=False),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "sport",
            "league",
            "market",
            name="uq_league_market_coverage",
        ),
    )

    op.create_index(
        op.f("ix_league_market_coverage_snapshots_sport"),
        "league_market_coverage_snapshots",
        ["sport"],
    )

    op.create_index(
        op.f("ix_league_market_coverage_snapshots_league"),
        "league_market_coverage_snapshots",
        ["league"],
    )

    op.create_index(
        op.f("ix_league_market_coverage_snapshots_market"),
        "league_market_coverage_snapshots",
        ["market"],
    )

    op.create_index(
        op.f("ix_league_market_coverage_snapshots_market_tier"),
        "league_market_coverage_snapshots",
        ["market_tier"],
    )

    op.create_index(
        op.f("ix_league_market_coverage_snapshots_production_allowed"),
        "league_market_coverage_snapshots",
        ["production_allowed"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_league_market_coverage_snapshots_production_allowed"),
        table_name="league_market_coverage_snapshots",
    )

    op.drop_index(
        op.f("ix_league_market_coverage_snapshots_market_tier"),
        table_name="league_market_coverage_snapshots",
    )

    op.drop_index(
        op.f("ix_league_market_coverage_snapshots_market"),
        table_name="league_market_coverage_snapshots",
    )

    op.drop_index(
        op.f("ix_league_market_coverage_snapshots_league"),
        table_name="league_market_coverage_snapshots",
    )

    op.drop_index(
        op.f("ix_league_market_coverage_snapshots_sport"),
        table_name="league_market_coverage_snapshots",
    )

    op.drop_table("league_market_coverage_snapshots")