"""add historical backtest bet cache

Revision ID: hist_bt_cache
Revises: repair_team_match_stats_columns
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa


revision = "hist_bt_cache"
down_revision = "repair_team_match_stats_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "historical_backtest_bets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_tag", sa.String(length=120), nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("league", sa.String(length=160), nullable=False),
        sa.Column("home_team", sa.String(length=160), nullable=False),
        sa.Column("away_team", sa.String(length=160), nullable=False),
        sa.Column("market", sa.String(length=80), nullable=False),
        sa.Column("predicted_label", sa.String(length=80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("odds", sa.Float(), nullable=True),
        sa.Column("implied_probability", sa.Float(), nullable=True),
        sa.Column("value_score", sa.Float(), nullable=True),
        sa.Column("won", sa.Boolean(), nullable=False),
        sa.Column("profit", sa.Float(), nullable=False),
        sa.Column("bankroll_after_bet", sa.Float(), nullable=False),
        sa.Column("stake", sa.Float(), nullable=False, server_default="100.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint(
            "run_tag",
            "market",
            "match_id",
            "predicted_label",
            name="uq_historical_backtest_bet_unique",
        ),
    )

    op.create_index(
        "ix_historical_backtest_bets_run_tag",
        "historical_backtest_bets",
        ["run_tag"],
        unique=False,
    )

    op.create_index(
        "ix_historical_backtest_bets_match_id",
        "historical_backtest_bets",
        ["match_id"],
        unique=False,
    )

    op.create_index(
        "ix_historical_backtest_bets_market",
        "historical_backtest_bets",
        ["market"],
        unique=False,
    )

    op.create_index(
        "ix_historical_backtest_bets_league",
        "historical_backtest_bets",
        ["league"],
        unique=False,
    )

    op.create_index(
        "ix_historical_backtest_bets_confidence",
        "historical_backtest_bets",
        ["confidence"],
        unique=False,
    )

    op.create_index(
        "ix_historical_backtest_bets_odds",
        "historical_backtest_bets",
        ["odds"],
        unique=False,
    )

    op.create_index(
        "ix_historical_backtest_bets_value_score",
        "historical_backtest_bets",
        ["value_score"],
        unique=False,
    )

    op.create_index(
        "ix_historical_backtest_bets_won",
        "historical_backtest_bets",
        ["won"],
        unique=False,
    )

    op.create_index(
        "ix_historical_backtest_bets_created_at",
        "historical_backtest_bets",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_historical_backtest_bets_created_at", table_name="historical_backtest_bets")
    op.drop_index("ix_historical_backtest_bets_won", table_name="historical_backtest_bets")
    op.drop_index("ix_historical_backtest_bets_value_score", table_name="historical_backtest_bets")
    op.drop_index("ix_historical_backtest_bets_odds", table_name="historical_backtest_bets")
    op.drop_index("ix_historical_backtest_bets_confidence", table_name="historical_backtest_bets")
    op.drop_index("ix_historical_backtest_bets_league", table_name="historical_backtest_bets")
    op.drop_index("ix_historical_backtest_bets_market", table_name="historical_backtest_bets")
    op.drop_index("ix_historical_backtest_bets_match_id", table_name="historical_backtest_bets")
    op.drop_index("ix_historical_backtest_bets_run_tag", table_name="historical_backtest_bets")

    op.drop_table("historical_backtest_bets")