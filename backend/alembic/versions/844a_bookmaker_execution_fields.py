"""add bookmaker execution intelligence fields

Revision ID: 844a_bookmaker_execution_fields
Revises: 843a_tournament_context_fields
Create Date: 2026-05-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "844a_bookmaker_execution_fields"
down_revision = "843a_tournament_context_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("predictions", sa.Column("execution_market", sa.String(length=120), nullable=True))
    op.add_column("predictions", sa.Column("execution_selection", sa.String(length=120), nullable=True))
    op.add_column("predictions", sa.Column("execution_family", sa.String(length=80), nullable=True))
    op.add_column("predictions", sa.Column("execution_line", sa.Float(), nullable=True))

    op.add_column("predictions", sa.Column("bookmaker_locality", sa.String(length=40), nullable=True))
    op.add_column("predictions", sa.Column("local_realism_score", sa.Float(), nullable=True))
    op.add_column("predictions", sa.Column("execution_score", sa.Float(), nullable=True))
    op.add_column("predictions", sa.Column("survivability_score", sa.Float(), nullable=True))
    op.add_column("predictions", sa.Column("execution_ready", sa.Boolean(), nullable=True))

    op.add_column(
        "predictions",
        sa.Column(
            "execution_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    op.add_column(
        "predictions",
        sa.Column(
            "market_alternatives",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    op.create_index("ix_predictions_execution_market", "predictions", ["execution_market"])
    op.create_index("ix_predictions_execution_selection", "predictions", ["execution_selection"])
    op.create_index("ix_predictions_execution_family", "predictions", ["execution_family"])
    op.create_index("ix_predictions_bookmaker_locality", "predictions", ["bookmaker_locality"])
    op.create_index("ix_predictions_execution_score", "predictions", ["execution_score"])
    op.create_index("ix_predictions_survivability_score", "predictions", ["survivability_score"])
    op.create_index("ix_predictions_execution_ready", "predictions", ["execution_ready"])


def downgrade() -> None:
    op.drop_index("ix_predictions_execution_ready", table_name="predictions")
    op.drop_index("ix_predictions_survivability_score", table_name="predictions")
    op.drop_index("ix_predictions_execution_score", table_name="predictions")
    op.drop_index("ix_predictions_bookmaker_locality", table_name="predictions")
    op.drop_index("ix_predictions_execution_family", table_name="predictions")
    op.drop_index("ix_predictions_execution_selection", table_name="predictions")
    op.drop_index("ix_predictions_execution_market", table_name="predictions")

    op.drop_column("predictions", "market_alternatives")
    op.drop_column("predictions", "execution_reasons")
    op.drop_column("predictions", "execution_ready")
    op.drop_column("predictions", "survivability_score")
    op.drop_column("predictions", "execution_score")
    op.drop_column("predictions", "local_realism_score")
    op.drop_column("predictions", "bookmaker_locality")
    op.drop_column("predictions", "execution_line")
    op.drop_column("predictions", "execution_family")
    op.drop_column("predictions", "execution_selection")
    op.drop_column("predictions", "execution_market")