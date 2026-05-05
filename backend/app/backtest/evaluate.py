# backend/app/backtest/evaluate.py

from sqlalchemy import text
from sqlalchemy.orm import Session


def evaluate_slate_by_group(session: Session, slate: str) -> list[dict]:
    query = text(
        """
        SELECT
            pgi.group_name,
            COUNT(*) AS picks,
            ROUND(
                AVG(
                    CASE
                        WHEN p.predicted_label = 'HOME_WIN'
                             AND m.home_goals > m.away_goals
                        THEN 1.0

                        WHEN p.predicted_label = 'NOT_HOME_WIN'
                             AND m.home_goals <= m.away_goals
                        THEN 1.0

                        ELSE 0.0
                    END
                ),
                4
            ) AS accuracy
        FROM prediction_group_items pgi
        JOIN predictions p
            ON p.id = pgi.prediction_id
        JOIN matches m
            ON m.id = p.match_id
        WHERE pgi.slate = :slate
          AND m.home_goals IS NOT NULL
          AND m.away_goals IS NOT NULL
        GROUP BY pgi.group_name
        ORDER BY pgi.group_name ASC
        """
    )

    rows = session.execute(query, {"slate": slate}).mappings().all()

    return [dict(row) for row in rows]