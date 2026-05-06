"""real ingestion foundation

Revision ID: 0002_real_ingestion_foundation
Revises: 0001_initial_sportslab_schema
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_real_ingestion_foundation"
down_revision = "0001_initial_sportslab_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "countries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=10), nullable=True),
        sa.Column("continent", sa.String(length=60), nullable=True),
    )
    op.create_index("ix_countries_name", "countries", ["name"], unique=True)
    op.create_index("ix_countries_code", "countries", ["code"])

    op.create_table(
        "competitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sport", sa.String(length=30), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_competition_id", sa.String(length=80), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("country_id", sa.Integer(), sa.ForeignKey("countries.id"), nullable=True),
        sa.Column("competition_type", sa.String(length=40), nullable=True),
        sa.Column("is_cup", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("provider", "provider_competition_id", name="uq_competition_provider_id"),
    )
    op.create_index("ix_competitions_sport", "competitions", ["sport"])
    op.create_index("ix_competitions_provider", "competitions", ["provider"])
    op.create_index("ix_competitions_name", "competitions", ["name"])
    op.create_index("ix_competitions_country_id", "competitions", ["country_id"])

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_team_id", sa.String(length=80), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=False),
        sa.Column("country_id", sa.Integer(), sa.ForeignKey("countries.id"), nullable=True),
        sa.Column("is_national_team", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("provider", "provider_team_id", name="uq_team_provider_id"),
    )
    op.create_index("ix_teams_provider", "teams", ["provider"])
    op.create_index("ix_teams_name", "teams", ["name"])
    op.create_index("ix_teams_normalized_name", "teams", ["normalized_name"])
    op.create_index("ix_teams_country_id", "teams", ["country_id"])

    op.add_column("matches", sa.Column("competition_id", sa.Integer(), nullable=True))
    op.add_column("matches", sa.Column("home_team_id", sa.Integer(), nullable=True))
    op.add_column("matches", sa.Column("away_team_id", sa.Integer(), nullable=True))
    op.add_column("matches", sa.Column("status", sa.String(length=40), nullable=False, server_default="scheduled"))
    op.add_column("matches", sa.Column("round_name", sa.String(length=120), nullable=True))
    op.add_column("matches", sa.Column("kickoff_datetime", sa.DateTime(), nullable=True))
    op.add_column("matches", sa.Column("is_finished", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("matches", sa.Column("is_postponed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("matches", sa.Column("is_cancelled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("matches", sa.Column("has_stats", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("matches", sa.Column("has_odds", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("matches", sa.Column("is_valid_for_training", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("matches", sa.Column("last_synced_at", sa.DateTime(), nullable=True))

    op.create_foreign_key("fk_matches_competition_id", "matches", "competitions", ["competition_id"], ["id"])
    op.create_foreign_key("fk_matches_home_team_id", "matches", "teams", ["home_team_id"], ["id"])
    op.create_foreign_key("fk_matches_away_team_id", "matches", "teams", ["away_team_id"], ["id"])

    op.create_index("ix_matches_competition_id", "matches", ["competition_id"])
    op.create_index("ix_matches_home_team_id", "matches", ["home_team_id"])
    op.create_index("ix_matches_away_team_id", "matches", ["away_team_id"])
    op.create_index("ix_matches_status", "matches", ["status"])
    op.create_index("ix_matches_kickoff_datetime", "matches", ["kickoff_datetime"])
    op.create_index("ix_matches_is_finished", "matches", ["is_finished"])
    op.create_index("ix_matches_is_postponed", "matches", ["is_postponed"])
    op.create_index("ix_matches_is_cancelled", "matches", ["is_cancelled"])
    op.create_index("ix_matches_is_valid_for_training", "matches", ["is_valid_for_training"])

    op.create_table(
        "provider_sync_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("sync_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="started"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("records_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_provider_sync_logs_provider", "provider_sync_logs", ["provider"])
    op.create_index("ix_provider_sync_logs_sync_type", "provider_sync_logs", ["sync_type"])
    op.create_index("ix_provider_sync_logs_status", "provider_sync_logs", ["status"])
    op.create_index("ix_provider_sync_logs_started_at", "provider_sync_logs", ["started_at"])

    op.create_table(
        "odds_market_maps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_market_name", sa.String(length=160), nullable=False),
        sa.Column("provider_selection_name", sa.String(length=160), nullable=False),
        sa.Column("internal_market", sa.String(length=80), nullable=False),
        sa.Column("internal_selection", sa.String(length=80), nullable=False),
        sa.Column("line_value", sa.Float(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint(
            "provider",
            "provider_market_name",
            "provider_selection_name",
            name="uq_odds_market_provider_mapping",
        ),
    )
    op.create_index("ix_odds_market_maps_provider", "odds_market_maps", ["provider"])
    op.create_index("ix_odds_market_maps_provider_market_name", "odds_market_maps", ["provider_market_name"])
    op.create_index("ix_odds_market_maps_provider_selection_name", "odds_market_maps", ["provider_selection_name"])
    op.create_index("ix_odds_market_maps_internal_market", "odds_market_maps", ["internal_market"])
    op.create_index("ix_odds_market_maps_internal_selection", "odds_market_maps", ["internal_selection"])


def downgrade() -> None:
    op.drop_table("odds_market_maps")
    op.drop_table("provider_sync_logs")

    op.drop_index("ix_matches_is_valid_for_training", table_name="matches")
    op.drop_index("ix_matches_is_cancelled", table_name="matches")
    op.drop_index("ix_matches_is_postponed", table_name="matches")
    op.drop_index("ix_matches_is_finished", table_name="matches")
    op.drop_index("ix_matches_kickoff_datetime", table_name="matches")
    op.drop_index("ix_matches_status", table_name="matches")
    op.drop_index("ix_matches_away_team_id", table_name="matches")
    op.drop_index("ix_matches_home_team_id", table_name="matches")
    op.drop_index("ix_matches_competition_id", table_name="matches")

    op.drop_constraint("fk_matches_away_team_id", "matches", type_="foreignkey")
    op.drop_constraint("fk_matches_home_team_id", "matches", type_="foreignkey")
    op.drop_constraint("fk_matches_competition_id", "matches", type_="foreignkey")

    op.drop_column("matches", "last_synced_at")
    op.drop_column("matches", "is_valid_for_training")
    op.drop_column("matches", "has_odds")
    op.drop_column("matches", "has_stats")
    op.drop_column("matches", "is_cancelled")
    op.drop_column("matches", "is_postponed")
    op.drop_column("matches", "is_finished")
    op.drop_column("matches", "kickoff_datetime")
    op.drop_column("matches", "round_name")
    op.drop_column("matches", "status")
    op.drop_column("matches", "away_team_id")
    op.drop_column("matches", "home_team_id")
    op.drop_column("matches", "competition_id")

    op.drop_table("teams")
    op.drop_table("competitions")
    op.drop_table("countries")