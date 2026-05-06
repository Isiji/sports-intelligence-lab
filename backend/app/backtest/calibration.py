# backend/app/backtest/calibration.py

from sqlalchemy import text
from sqlalchemy.orm import Session


def evaluate_confidence_calibration(session: Session, slate: str) -> list[dict]:
    query = text(
        """
        WITH scored AS (
            SELECT
                p.confidence,
                CASE
                    WHEN p.predicted_label = 'HOME_WIN' AND m.home_goals > m.away_goals THEN 1
                    WHEN p.predicted_label = 'NOT_HOME_WIN' AND m.home_goals <= m.away_goals THEN 1

                    WHEN p.predicted_label = 'AWAY_WIN' AND m.away_goals > m.home_goals THEN 1
                    WHEN p.predicted_label = 'NOT_AWAY_WIN' AND m.away_goals <= m.home_goals THEN 1

                    WHEN p.predicted_label = 'DRAW' AND m.home_goals = m.away_goals THEN 1
                    WHEN p.predicted_label = 'NOT_DRAW' AND m.home_goals != m.away_goals THEN 1

                    WHEN p.predicted_label = 'DOUBLE_CHANCE_1X' AND m.home_goals >= m.away_goals THEN 1
                    WHEN p.predicted_label = 'DOUBLE_CHANCE_X2' AND m.away_goals >= m.home_goals THEN 1
                    WHEN p.predicted_label = 'DOUBLE_CHANCE_12' AND m.home_goals != m.away_goals THEN 1

                    WHEN p.predicted_label = 'OVER_2_5' AND (m.home_goals + m.away_goals) > 2 THEN 1
                    WHEN p.predicted_label = 'UNDER_2_5' AND (m.home_goals + m.away_goals) <= 2 THEN 1

                    WHEN p.predicted_label = 'BTTS_YES' AND m.home_goals > 0 AND m.away_goals > 0 THEN 1
                    WHEN p.predicted_label = 'BTTS_NO' AND (m.home_goals = 0 OR m.away_goals = 0) THEN 1

                    ELSE 0
                END AS correct
            FROM predictions p
            JOIN matches m ON m.id = p.match_id
            WHERE p.slate = :slate
              AND m.home_goals IS NOT NULL
              AND m.away_goals IS NOT NULL
        )
        SELECT
            CASE
                WHEN confidence >= 0.9 THEN '90-100%'
                WHEN confidence >= 0.8 THEN '80-90%'
                WHEN confidence >= 0.7 THEN '70-80%'
                WHEN confidence >= 0.6 THEN '60-70%'
                ELSE '50-60%'
            END AS bucket,
            COUNT(*) AS total_predictions,
            SUM(correct) AS correct_predictions,
            ROUND(AVG(correct::numeric), 4) AS accuracy,
            ROUND(AVG(confidence::numeric), 4) AS average_confidence
        FROM scored
        GROUP BY bucket
        ORDER BY bucket
        """
    )

    rows = session.execute(query, {"slate": slate}).mappings().all()

    return [dict(row) for row in rows]