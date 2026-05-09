# backend/app/backtest/calibration.py

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def evaluate_confidence_calibration(
    session: Session,
    slate: str,
) -> list[dict]:
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

                    WHEN p.predicted_label = 'OVER_1_5' AND (m.home_goals + m.away_goals) > 1 THEN 1
                    WHEN p.predicted_label = 'UNDER_1_5' AND (m.home_goals + m.away_goals) <= 1 THEN 1

                    WHEN p.predicted_label = 'OVER_2_5' AND (m.home_goals + m.away_goals) > 2 THEN 1
                    WHEN p.predicted_label = 'UNDER_2_5' AND (m.home_goals + m.away_goals) <= 2 THEN 1

                    WHEN p.predicted_label = 'OVER_3_5' AND (m.home_goals + m.away_goals) > 3 THEN 1
                    WHEN p.predicted_label = 'UNDER_3_5' AND (m.home_goals + m.away_goals) <= 3 THEN 1

                    WHEN p.predicted_label = 'BTTS_YES' AND m.home_goals > 0 AND m.away_goals > 0 THEN 1
                    WHEN p.predicted_label = 'BTTS_NO' AND (m.home_goals = 0 OR m.away_goals = 0) THEN 1

                    ELSE 0
                END AS correct
            FROM predictions p
            JOIN matches m
                ON m.id = p.match_id
            WHERE p.slate = :slate
              AND m.home_goals IS NOT NULL
              AND m.away_goals IS NOT NULL
        )
        SELECT
            CASE
                WHEN confidence >= 0.95 THEN '95-100%'
                WHEN confidence >= 0.90 THEN '90-95%'
                WHEN confidence >= 0.80 THEN '80-90%'
                WHEN confidence >= 0.70 THEN '70-80%'
                WHEN confidence >= 0.60 THEN '60-70%'
                ELSE '0-60%'
            END AS bucket,
            COUNT(*) AS total_predictions,
            SUM(correct) AS correct_predictions,
            ROUND(AVG(correct::numeric), 4) AS accuracy,
            ROUND(AVG(confidence::numeric), 4) AS average_confidence,
            ROUND((AVG(confidence::numeric) - AVG(correct::numeric)), 4) AS overconfidence_gap
        FROM scored
        GROUP BY bucket
        ORDER BY bucket
        """
    )

    rows = session.execute(
        query,
        {"slate": slate},
    ).mappings().all()

    return [dict(row) for row in rows]


def evaluate_cached_backtest_calibration(
    session: Session,
    run_tag: str,
    market: str | None = None,
) -> list[dict]:
    filters = ["run_tag = :run_tag"]

    params = {
        "run_tag": run_tag,
    }

    if market:
        filters.append("market = :market")
        params["market"] = market

    where_sql = " AND ".join(filters)

    query = text(
        f"""
        SELECT
            CASE
                WHEN confidence >= 0.95 THEN '95-100%'
                WHEN confidence >= 0.90 THEN '90-95%'
                WHEN confidence >= 0.80 THEN '80-90%'
                WHEN confidence >= 0.70 THEN '70-80%'
                WHEN confidence >= 0.60 THEN '60-70%'
                ELSE '0-60%'
            END AS bucket,

            COUNT(*) AS total_bets,

            SUM(
                CASE WHEN won = true THEN 1 ELSE 0 END
            ) AS winning_bets,

            ROUND(
                AVG(
                    CASE WHEN won = true THEN 1.0 ELSE 0.0 END
                )::numeric,
                4
            ) AS actual_hit_rate,

            ROUND(
                AVG(confidence)::numeric,
                4
            ) AS average_confidence,

            ROUND(
                (
                    AVG(confidence)
                    -
                    AVG(
                        CASE WHEN won = true THEN 1.0 ELSE 0.0 END
                    )
                )::numeric,
                4
            ) AS overconfidence_gap,

            ROUND(
                (
                    SUM(profit)
                    / NULLIF(SUM(stake), 0)
                )::numeric,
                4
            ) AS roi

        FROM historical_backtest_bets

        WHERE {where_sql}

        GROUP BY bucket

        ORDER BY bucket
        """
    )

    rows = session.execute(
        query,
        params,
    ).mappings().all()

    return [dict(row) for row in rows]


def evaluate_cached_backtest_calibration_by_market(
    session: Session,
    run_tag: str,
    min_bets: int = 20,
) -> list[dict]:
    query = text(
        """
        SELECT
            market,

            COUNT(*) AS total_bets,

            ROUND(
                AVG(confidence)::numeric,
                4
            ) AS average_confidence,

            ROUND(
                AVG(
                    CASE WHEN won = true THEN 1.0 ELSE 0.0 END
                )::numeric,
                4
            ) AS actual_hit_rate,

            ROUND(
                (
                    AVG(confidence)
                    -
                    AVG(
                        CASE WHEN won = true THEN 1.0 ELSE 0.0 END
                    )
                )::numeric,
                4
            ) AS overconfidence_gap,

            ROUND(
                (
                    SUM(profit)
                    / NULLIF(SUM(stake), 0)
                )::numeric,
                4
            ) AS roi

        FROM historical_backtest_bets

        WHERE run_tag = :run_tag

        GROUP BY market

        HAVING COUNT(*) >= :min_bets

        ORDER BY overconfidence_gap DESC
        """
    )

    rows = session.execute(
        query,
        {
            "run_tag": run_tag,
            "min_bets": min_bets,
        },
    ).mappings().all()

    return [dict(row) for row in rows]