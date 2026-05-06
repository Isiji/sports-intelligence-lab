# backend/app/reports/prediction_performance.py

from sqlalchemy import text
from sqlalchemy.orm import Session


def build_prediction_performance_report(session: Session, slate: str | None = None) -> dict:
    params = {}
    slate_filter = ""

    if slate:
        slate_filter = "AND p.slate = :slate"
        params["slate"] = slate

    summary_query = text(
        f"""
        WITH settled AS (
            SELECT
                p.id,
                p.market,
                p.predicted_label,
                p.confidence,
                m.home_goals,
                m.away_goals,
                CASE
                    WHEN m.home_goals IS NULL OR m.away_goals IS NULL THEN NULL
                    ELSE true
                END AS is_settled,
                CASE
                    WHEN m.home_goals IS NULL OR m.away_goals IS NULL THEN NULL

                    WHEN p.market = 'home_win'
                        THEN (p.predicted_label = 'HOME_WIN') = (m.home_goals > m.away_goals)

                    WHEN p.market = 'away_win'
                        THEN (p.predicted_label = 'AWAY_WIN') = (m.away_goals > m.home_goals)

                    WHEN p.market = 'draw'
                        THEN (p.predicted_label = 'DRAW') = (m.home_goals = m.away_goals)

                    WHEN p.market = 'double_chance_1x'
                        THEN (p.predicted_label = 'DOUBLE_CHANCE_1X') = (m.home_goals >= m.away_goals)

                    WHEN p.market = 'double_chance_x2'
                        THEN (p.predicted_label = 'DOUBLE_CHANCE_X2') = (m.away_goals >= m.home_goals)

                    WHEN p.market = 'double_chance_12'
                        THEN (p.predicted_label = 'DOUBLE_CHANCE_12') = (m.home_goals != m.away_goals)

                    WHEN p.market = 'over_2_5_goals'
                        THEN (p.predicted_label = 'OVER_2_5') = ((m.home_goals + m.away_goals) > 2.5)

                    WHEN p.market = 'under_2_5_goals'
                        THEN (p.predicted_label = 'UNDER_2_5') = ((m.home_goals + m.away_goals) <= 2.5)

                    WHEN p.market = 'btts_yes'
                        THEN (p.predicted_label = 'BTTS_YES') = (m.home_goals > 0 AND m.away_goals > 0)

                    WHEN p.market = 'btts_no'
                        THEN (p.predicted_label = 'BTTS_NO') = (m.home_goals = 0 OR m.away_goals = 0)

                    ELSE NULL
                END AS is_correct
            FROM predictions p
            JOIN matches m ON m.id = p.match_id
            WHERE 1 = 1
            {slate_filter}
        )
        SELECT
            COUNT(*) AS total_predictions,
            COUNT(CASE WHEN is_settled = true THEN 1 END) AS settled_predictions,
            COUNT(CASE WHEN is_settled IS NULL THEN 1 END) AS pending_predictions,
            COUNT(CASE WHEN is_correct = true THEN 1 END) AS correct_predictions,
            COUNT(CASE WHEN is_correct = false THEN 1 END) AS wrong_predictions,
            ROUND(
                COUNT(CASE WHEN is_correct = true THEN 1 END)::numeric
                / NULLIF(COUNT(CASE WHEN is_correct IS NOT NULL THEN 1 END), 0),
                4
            ) AS accuracy,
            ROUND(AVG(confidence)::numeric, 4) AS avg_confidence
        FROM settled
        """
    )

    market_query = text(
        f"""
        WITH settled AS (
            SELECT
                p.id,
                p.market,
                p.predicted_label,
                p.confidence,
                m.home_goals,
                m.away_goals,
                CASE
                    WHEN m.home_goals IS NULL OR m.away_goals IS NULL THEN NULL

                    WHEN p.market = 'home_win'
                        THEN (p.predicted_label = 'HOME_WIN') = (m.home_goals > m.away_goals)

                    WHEN p.market = 'away_win'
                        THEN (p.predicted_label = 'AWAY_WIN') = (m.away_goals > m.home_goals)

                    WHEN p.market = 'draw'
                        THEN (p.predicted_label = 'DRAW') = (m.home_goals = m.away_goals)

                    WHEN p.market = 'double_chance_1x'
                        THEN (p.predicted_label = 'DOUBLE_CHANCE_1X') = (m.home_goals >= m.away_goals)

                    WHEN p.market = 'double_chance_x2'
                        THEN (p.predicted_label = 'DOUBLE_CHANCE_X2') = (m.away_goals >= m.home_goals)

                    WHEN p.market = 'double_chance_12'
                        THEN (p.predicted_label = 'DOUBLE_CHANCE_12') = (m.home_goals != m.away_goals)

                    WHEN p.market = 'over_2_5_goals'
                        THEN (p.predicted_label = 'OVER_2_5') = ((m.home_goals + m.away_goals) > 2.5)

                    WHEN p.market = 'under_2_5_goals'
                        THEN (p.predicted_label = 'UNDER_2_5') = ((m.home_goals + m.away_goals) <= 2.5)

                    WHEN p.market = 'btts_yes'
                        THEN (p.predicted_label = 'BTTS_YES') = (m.home_goals > 0 AND m.away_goals > 0)

                    WHEN p.market = 'btts_no'
                        THEN (p.predicted_label = 'BTTS_NO') = (m.home_goals = 0 OR m.away_goals = 0)

                    ELSE NULL
                END AS is_correct
            FROM predictions p
            JOIN matches m ON m.id = p.match_id
            WHERE 1 = 1
            {slate_filter}
        )
        SELECT
            market,
            COUNT(*) AS total_predictions,
            COUNT(CASE WHEN home_goals IS NOT NULL AND away_goals IS NOT NULL THEN 1 END) AS settled_predictions,
            COUNT(CASE WHEN is_correct = true THEN 1 END) AS correct_predictions,
            COUNT(CASE WHEN is_correct = false THEN 1 END) AS wrong_predictions,
            ROUND(
                COUNT(CASE WHEN is_correct = true THEN 1 END)::numeric
                / NULLIF(COUNT(CASE WHEN is_correct IS NOT NULL THEN 1 END), 0),
                4
            ) AS accuracy,
            ROUND(AVG(confidence)::numeric, 4) AS avg_confidence
        FROM settled
        GROUP BY market
        ORDER BY accuracy DESC NULLS LAST, settled_predictions DESC
        """
    )

    summary = session.execute(summary_query, params).mappings().first()
    markets = session.execute(market_query, params).mappings().all()

    return {
        "summary": dict(summary or {}),
        "markets": [dict(row) for row in markets],
    }