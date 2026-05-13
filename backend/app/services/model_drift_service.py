# backend/app/services/model_drift_service.py

from dataclasses import dataclass
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DriftDecision:
    should_retrain: bool
    reason: str
    settled_predictions: int
    recent_accuracy: float | None


class ModelDriftService:
    """
    Detects when model quality is stale or dropping.

    Production-safe:
    - Does not retrain blindly.
    - Requires enough settled predictions.
    """

    def __init__(
        self,
        min_settled_predictions: int = 100,
        min_recent_accuracy: float = 0.52,
    ):
        self.min_settled_predictions = min_settled_predictions
        self.min_recent_accuracy = min_recent_accuracy

    def check_drift(self, session: Session) -> DriftDecision:
        row = session.execute(
            text(
                """
                SELECT
                    COUNT(*) AS settled_predictions,
                    AVG(
                        CASE
                            WHEN is_correct = true THEN 1.0
                            WHEN is_correct = false THEN 0.0
                            ELSE NULL
                        END
                    ) AS recent_accuracy
                FROM predictions
                WHERE is_correct IS NOT NULL
                  AND created_at >= NOW() - INTERVAL '14 days'
                """
            )
        ).mappings().first()

        settled = int(row["settled_predictions"] or 0)
        accuracy = row["recent_accuracy"]

        if settled < self.min_settled_predictions:
            return DriftDecision(
                should_retrain=False,
                reason="Not enough recent settled predictions for reliable drift decision.",
                settled_predictions=settled,
                recent_accuracy=float(accuracy) if accuracy is not None else None,
            )

        if accuracy is not None and float(accuracy) < self.min_recent_accuracy:
            return DriftDecision(
                should_retrain=True,
                reason="Recent prediction accuracy dropped below safe threshold.",
                settled_predictions=settled,
                recent_accuracy=float(accuracy),
            )

        return DriftDecision(
            should_retrain=False,
            reason="No retraining needed.",
            settled_predictions=settled,
            recent_accuracy=float(accuracy) if accuracy is not None else None,
        )