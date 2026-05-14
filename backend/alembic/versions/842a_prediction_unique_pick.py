"""add prediction unique pick constraint

Revision ID: 842a_prediction_unique_pick
Revises: 841a_prediction_odds_source
Create Date: 2026-05-17 00:00:00.000000
"""

from alembic import op


revision = "842a_prediction_unique_pick"
down_revision = "841a_prediction_odds_source"
branch_labels = None
depends_on = None


def upgrade() -> None:

    # =====================================================
    # REMOVE GROUP ITEMS POINTING TO DUPLICATE PREDICTIONS
    # =====================================================

    op.execute("""
        DELETE FROM prediction_group_items pgi
        USING predictions a, predictions b
        WHERE pgi.prediction_id = a.id
          AND a.id < b.id
          AND a.slate = b.slate
          AND a.match_id = b.match_id
          AND a.market = b.market
          AND a.predicted_label = b.predicted_label;
    """)

    # =====================================================
    # REMOVE DUPLICATE PREDICTIONS
    # =====================================================

    op.execute("""
        DELETE FROM predictions a
        USING predictions b
        WHERE a.id < b.id
          AND a.slate = b.slate
          AND a.match_id = b.match_id
          AND a.market = b.market
          AND a.predicted_label = b.predicted_label;
    """)

    # =====================================================
    # ADD UNIQUE CONSTRAINT
    # =====================================================

    op.execute("""
        ALTER TABLE predictions
        ADD CONSTRAINT uq_prediction_unique_pick
        UNIQUE (
            slate,
            match_id,
            market,
            predicted_label
        );
    """)

def downgrade() -> None:
    op.execute("""
        ALTER TABLE predictions
        DROP CONSTRAINT IF EXISTS uq_prediction_unique_pick;
    """)