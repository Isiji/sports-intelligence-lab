# backend/app/analysis/weak_markets.py

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_weak_markets(
    session: Session,
    min_accuracy: float = 0.58,
    min_f1: float = 0.45,
    min_picks: int = 5,
) -> list[dict]:
    query = text(
        """
        SELECT
            market,
            model_name,
            accuracy,
            f1,
            brier_score,
            roc_auc,
            test_size,
            created_at
        FROM model_training_runs
        WHERE selected = 1
        ORDER BY created_at DESC
        """
    )

    rows = session.execute(query).mappings().all()

    latest_by_market = {}

    for row in rows:
        market = row["market"]
        if market not in latest_by_market:
            latest_by_market[market] = dict(row)

    weak = []

    for market, row in latest_by_market.items():
        reasons = []

        if row["accuracy"] < min_accuracy:
            reasons.append("low_accuracy")

        if row["f1"] < min_f1:
            reasons.append("low_f1")

        if row["test_size"] < min_picks:
            reasons.append("low_test_sample")

        if reasons:
            weak.append(
                {
                    **row,
                    "reasons": reasons,
                    "recommended_action": "skip_or_require_higher_confidence",
                }
            )

    return weak


def is_market_weak(session: Session, market: str) -> bool:
    weak = get_weak_markets(session=session)
    return any(row["market"] == market for row in weak)