"""initial sportslab schema

Revision ID: 0001_initial_sportslab_schema
Revises:
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_sportslab_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sport", sa.String(length=30), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("provider_fixture_id", sa.String(length=80), nullable=True),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("league", sa.String(length=120), nullable=False),
        sa.Column("home_team", sa.String(length=120), nullable=False),
        sa.Column("away_team", sa.String(length=120), nullable=False),
        sa.Column("kickoff_date", sa.Date(), nullable=False),
        sa.Column("home_goals", sa.Integer(), nullable=True),
        sa.Column("away_goals", sa.Integer(), nullable=True),
        sa.UniqueConstraint(
            "provider",
            "provider_fixture_id",
            name="uq_match_provider_fixture",
        ),
    )

    op.create_index("ix_matches_sport", "matches", ["sport"])
    op.create_index("ix_matches_provider", "matches", ["provider"])
    op.create_index("ix_matches_league", "matches", ["league"])
    op.create_index("ix_matches_home_team", "matches", ["home_team"])
    op.create_index("ix_matches_away_team", "matches", ["away_team"])
    op.create_index("ix_matches_kickoff_date", "matches", ["kickoff_date"])

    op.create_table(
        "team_match_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("team", sa.String(length=120), nullable=False),
        sa.Column("is_home", sa.Integer(), nullable=False),
        sa.Column("goals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("corners", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shots_on_target", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("possession", sa.Float(), nullable=False, server_default="0"),
        sa.Column("fouls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cards", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("keeper_saves", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_index("ix_team_match_stats_match_id", "team_match_stats", ["match_id"])
    op.create_index("ix_team_match_stats_team", "team_match_stats", ["team"])

    op.create_table(
        "match_odds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("bookmaker", sa.String(length=80), nullable=True),
        sa.Column("market", sa.String(length=80), nullable=False),
        sa.Column("selection", sa.String(length=80), nullable=False),
        sa.Column("odds", sa.Float(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_match_odds_match_id", "match_odds", ["match_id"])
    op.create_index("ix_match_odds_provider", "match_odds", ["provider"])
    op.create_index("ix_match_odds_market", "match_odds", ["market"])
    op.create_index("ix_match_odds_selection", "match_odds", ["selection"])
    op.create_index("ix_match_odds_retrieved_at", "match_odds", ["retrieved_at"])

    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slate", sa.String(length=100), nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("sport", sa.String(length=30), nullable=False),
        sa.Column("model_name", sa.String(length=80), nullable=False),
        sa.Column("market", sa.String(length=80), nullable=False),
        sa.Column("predicted_label", sa.String(length=80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("odds", sa.Float(), nullable=True),
        sa.Column("implied_probability", sa.Float(), nullable=True),
        sa.Column("value_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_predictions_slate", "predictions", ["slate"])
    op.create_index("ix_predictions_match_id", "predictions", ["match_id"])
    op.create_index("ix_predictions_sport", "predictions", ["sport"])
    op.create_index("ix_predictions_market", "predictions", ["market"])

    op.create_table(
        "prediction_group_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slate", sa.String(length=100), nullable=False),
        sa.Column("group_name", sa.String(length=30), nullable=False),
        sa.Column("prediction_id", sa.Integer(), sa.ForeignKey("predictions.id"), nullable=False),
    )

    op.create_index("ix_prediction_group_items_slate", "prediction_group_items", ["slate"])
    op.create_index("ix_prediction_group_items_group_name", "prediction_group_items", ["group_name"])
    op.create_index("ix_prediction_group_items_prediction_id", "prediction_group_items", ["prediction_id"])

    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slate", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("overall_accuracy", sa.Float(), nullable=False, server_default="0"),
        sa.Column("settled_predictions", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_index("ix_backtest_runs_slate", "backtest_runs", ["slate"])

    op.create_table(
        "api_call_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("endpoint", sa.String(length=120), nullable=False),
        sa.Column("called_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_api_call_logs_provider", "api_call_logs", ["provider"])
    op.create_index("ix_api_call_logs_called_at", "api_call_logs", ["called_at"])

    op.create_table(
        "model_training_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sport", sa.String(length=30), nullable=False),
        sa.Column("market", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("accuracy", sa.Float(), nullable=False, server_default="0"),
        sa.Column("precision", sa.Float(), nullable=False, server_default="0"),
        sa.Column("recall", sa.Float(), nullable=False, server_default="0"),
        sa.Column("f1", sa.Float(), nullable=False, server_default="0"),
        sa.Column("log_loss", sa.Float(), nullable=False, server_default="0"),
        sa.Column("brier_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("roc_auc", sa.Float(), nullable=False, server_default="0"),
        sa.Column("train_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("test_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("selected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_model_training_runs_sport", "model_training_runs", ["sport"])
    op.create_index("ix_model_training_runs_market", "model_training_runs", ["market"])
    op.create_index("ix_model_training_runs_model_name", "model_training_runs", ["model_name"])
    op.create_index("ix_model_training_runs_created_at", "model_training_runs", ["created_at"])


def downgrade() -> None:
    op.drop_table("model_training_runs")
    op.drop_table("api_call_logs")
    op.drop_table("backtest_runs")
    op.drop_table("prediction_group_items")
    op.drop_table("predictions")
    op.drop_table("match_odds")
    op.drop_table("team_match_stats")
    op.drop_table("matches")