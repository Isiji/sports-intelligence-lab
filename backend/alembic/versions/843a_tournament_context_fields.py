"""add tournament context fields

Revision ID: 843a_tournament_context_fields
Revises: 842a_prediction_unique_pick
Create Date: 2026-05-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "843a_tournament_context_fields"
down_revision = "842a_prediction_unique_pick"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("is_international", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("matches", sa.Column("is_neutral_venue", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("matches", sa.Column("tournament_type", sa.String(length=80), nullable=True))
    op.add_column("matches", sa.Column("tournament_stage", sa.String(length=80), nullable=True))
    op.add_column("matches", sa.Column("competition_priority", sa.Float(), nullable=False, server_default="0"))
    op.add_column("matches", sa.Column("tournament_pressure_score", sa.Float(), nullable=False, server_default="0"))

    op.create_index("ix_matches_is_international", "matches", ["is_international"])
    op.create_index("ix_matches_is_neutral_venue", "matches", ["is_neutral_venue"])
    op.create_index("ix_matches_tournament_type", "matches", ["tournament_type"])
    op.create_index("ix_matches_tournament_stage", "matches", ["tournament_stage"])


def downgrade() -> None:
    op.drop_index("ix_matches_tournament_stage", table_name="matches")
    op.drop_index("ix_matches_tournament_type", table_name="matches")
    op.drop_index("ix_matches_is_neutral_venue", table_name="matches")
    op.drop_index("ix_matches_is_international", table_name="matches")

    op.drop_column("matches", "tournament_pressure_score")
    op.drop_column("matches", "competition_priority")
    op.drop_column("matches", "tournament_stage")
    op.drop_column("matches", "tournament_type")
    op.drop_column("matches", "is_neutral_venue")
    op.drop_column("matches", "is_international")