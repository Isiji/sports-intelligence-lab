# backend/alembic/versions/836b71c7f1c4_add_prediction_settlement_fields.py

"""add_prediction_settlement_fields

Revision ID: 836b71c7f1c4
Revises: 835a19e09516
Create Date: 2026-05-11 16:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "836b71c7f1c4"
down_revision = "835a19e09516"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "predictions",
        sa.Column("is_correct", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "predictions",
        sa.Column("result_label", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "predictions",
        sa.Column("profit_loss", sa.Float(), nullable=True),
    )
    op.add_column(
        "predictions",
        sa.Column("stake", sa.Float(), nullable=True),
    )
    op.add_column(
        "predictions",
        sa.Column("settled_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "predictions",
        sa.Column("closing_odds", sa.Float(), nullable=True),
    )
    op.add_column(
        "predictions",
        sa.Column("clv", sa.Float(), nullable=True),
    )

    op.create_index(
        op.f("ix_predictions_is_correct"),
        "predictions",
        ["is_correct"],
        unique=False,
    )
    op.create_index(
        op.f("ix_predictions_result_label"),
        "predictions",
        ["result_label"],
        unique=False,
    )
    op.create_index(
        op.f("ix_predictions_settled_at"),
        "predictions",
        ["settled_at"],
        unique=False,
    )

    op.add_column(
        "prediction_outcomes",
        sa.Column("result_label", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "prediction_outcomes",
        sa.Column("closing_odds", sa.Float(), nullable=True),
    )
    op.add_column(
        "prediction_outcomes",
        sa.Column("clv", sa.Float(), nullable=True),
    )
    op.add_column(
        "prediction_outcomes",
        sa.Column(
            "stake",
            sa.Float(),
            nullable=False,
            server_default="100",
        ),
    )

    op.create_index(
        op.f("ix_prediction_outcomes_result_label"),
        "prediction_outcomes",
        ["result_label"],
        unique=False,
    )
    op.create_index(
        op.f("ix_prediction_outcomes_predicted_label"),
        "prediction_outcomes",
        ["predicted_label"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_prediction_outcomes_predicted_label"),
        table_name="prediction_outcomes",
    )
    op.drop_index(
        op.f("ix_prediction_outcomes_result_label"),
        table_name="prediction_outcomes",
    )

    op.drop_column("prediction_outcomes", "stake")
    op.drop_column("prediction_outcomes", "clv")
    op.drop_column("prediction_outcomes", "closing_odds")
    op.drop_column("prediction_outcomes", "result_label")

    op.drop_index(
        op.f("ix_predictions_settled_at"),
        table_name="predictions",
    )
    op.drop_index(
        op.f("ix_predictions_result_label"),
        table_name="predictions",
    )
    op.drop_index(
        op.f("ix_predictions_is_correct"),
        table_name="predictions",
    )

    op.drop_column("predictions", "clv")
    op.drop_column("predictions", "closing_odds")
    op.drop_column("predictions", "settled_at")
    op.drop_column("predictions", "stake")
    op.drop_column("predictions", "profit_loss")
    op.drop_column("predictions", "result_label")
    op.drop_column("predictions", "is_correct")