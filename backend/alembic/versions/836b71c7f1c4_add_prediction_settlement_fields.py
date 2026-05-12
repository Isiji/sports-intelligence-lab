# backend/alembic/versions/836b71c7f1c4_add_prediction_settlement_fields.py

"""add_prediction_settlement_fields

Revision ID: 836b71c7f1c4
Revises: 835a19e09516
"""

from alembic import op


revision = "836b71c7f1c4"
down_revision = "835a19e09516"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS is_correct BOOLEAN
    """)

    op.execute("""
    ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS result_label VARCHAR(80)
    """)

    op.execute("""
    ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS profit_loss FLOAT
    """)

    op.execute("""
    ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS stake FLOAT
    """)

    op.execute("""
    ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS settled_at TIMESTAMP
    """)

    op.execute("""
    ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS closing_odds FLOAT
    """)

    op.execute("""
    ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS clv FLOAT
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_predictions_is_correct
    ON predictions (is_correct)
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_predictions_result_label
    ON predictions (result_label)
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS ix_predictions_settled_at
    ON predictions (settled_at)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_predictions_settled_at")
    op.execute("DROP INDEX IF EXISTS ix_predictions_result_label")
    op.execute("DROP INDEX IF EXISTS ix_predictions_is_correct")

    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS clv")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS closing_odds")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS settled_at")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS stake")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS profit_loss")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS result_label")
    op.execute("ALTER TABLE predictions DROP COLUMN IF EXISTS is_correct")