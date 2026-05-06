# backend/app/backtest/evaluate.py

from sqlalchemy import text
from sqlalchemy.orm import Session


def evaluate_slate_by_group(session: Session, slate: str) -> list[dict]:
    query = text(
        """
        WITH scored AS (
            SELECT
                pgi.group_name,
                p.id AS prediction_id,
                p.market,
                p.predicted_label,
                p.confidence,
                p.odds,
                m.home_goals,
                m.away_goals,
                hs.corners AS home_corners,
                as1.corners AS away_corners,
                hs.shots_on_target AS home_sot,
                as1.shots_on_target AS away_sot,
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

                    WHEN p.predicted_label = 'CORNERS_OVER_8_5' AND (hs.corners + as1.corners) > 8 THEN 1
                    WHEN p.predicted_label = 'CORNERS_UNDER_8_5' AND (hs.corners + as1.corners) <= 8 THEN 1

                    WHEN p.predicted_label = 'SOT_OVER_8_5' AND (hs.shots_on_target + as1.shots_on_target) > 8 THEN 1
                    WHEN p.predicted_label = 'SOT_UNDER_8_5' AND (hs.shots_on_target + as1.shots_on_target) <= 8 THEN 1

                    ELSE 0
                END AS correct
            FROM prediction_group_items pgi
            JOIN predictions p ON p.id = pgi.prediction_id
            JOIN matches m ON m.id = p.match_id
            JOIN team_match_stats hs ON hs.match_id = m.id AND hs.is_home = 1
            JOIN team_match_stats as1 ON as1.match_id = m.id AND as1.is_home = 0
            WHERE pgi.slate = :slate
              AND m.home_goals IS NOT NULL
              AND m.away_goals IS NOT NULL
        )
        SELECT
            group_name,
            COUNT(*) AS picks,
            ROUND(AVG(correct::float), 4) AS accuracy,
            ROUND(AVG(confidence), 4) AS average_confidence,
            ROUND(EXP(SUM(LN(NULLIF(odds, 0)))), 4) AS cumulative_odds
        FROM scored
        GROUP BY group_name
        ORDER BY group_name ASC
        """
    )

    rows = session.execute(query, {"slate": slate}).mappings().all()

    return [dict(row) for row in rows]


def evaluate_slate_by_market(session: Session, slate: str) -> list[dict]:
    query = text(
        """
        WITH scored AS (
            SELECT
                p.market,
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
            market,
            COUNT(*) AS picks,
            ROUND(AVG(correct::float), 4) AS accuracy,
            ROUND(AVG(confidence), 4) AS average_confidence
        FROM scored
        GROUP BY market
        ORDER BY accuracy DESC, picks DESC
        """
    )

    rows = session.execute(query, {"slate": slate}).mappings().all()

    return [dict(row) for row in rows]