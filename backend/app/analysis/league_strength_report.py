from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def build_league_strength_report(session: Session, limit: int = 80) -> dict:
    summary = session.execute(
        text(
            """
            SELECT
                COUNT(*) AS total_matches,
                COUNT(*) FILTER (WHERE is_finished = true) AS finished_matches,
                COUNT(*) FILTER (WHERE has_stats = true) AS matches_with_stats,
                COUNT(*) FILTER (WHERE has_odds = true) AS matches_with_odds
            FROM matches
            """
        )
    ).mappings().first()

    leagues = session.execute(
        text(
            """
            WITH league_base AS (
                SELECT
                    m.league,
                    COUNT(*) AS total_matches,
                    COUNT(*) FILTER (WHERE m.is_finished = true) AS finished_matches,
                    COUNT(*) FILTER (WHERE m.has_stats = true) AS matches_with_stats,
                    COUNT(*) FILTER (WHERE m.has_odds = true) AS matches_with_odds,
                    COUNT(DISTINCT mo.market) AS distinct_odds_markets,
                    COUNT(mo.id) AS odds_rows
                FROM matches m
                LEFT JOIN match_odds mo
                    ON mo.match_id = m.id
                GROUP BY m.league
            )

            SELECT
                league,
                total_matches,
                finished_matches,
                matches_with_stats,
                matches_with_odds,
                distinct_odds_markets,
                odds_rows,

                ROUND(
                    CASE
                        WHEN total_matches = 0 THEN 0
                        ELSE matches_with_stats::numeric / total_matches
                    END,
                    4
                ) AS stats_coverage,

                ROUND(
                    CASE
                        WHEN total_matches = 0 THEN 0
                        ELSE matches_with_odds::numeric / total_matches
                    END,
                    4
                ) AS odds_coverage,

                ROUND(
                    (
                        LEAST(matches_with_stats::numeric / NULLIF(total_matches, 0), 1) * 0.30
                        +
                        LEAST(matches_with_odds::numeric / NULLIF(total_matches, 0), 1) * 0.40
                        +
                        LEAST(distinct_odds_markets::numeric / 20, 1) * 0.20
                        +
                        LEAST(finished_matches::numeric / 300, 1) * 0.10
                    ),
                    4
                ) AS league_strength_score,

                CASE
                    WHEN
                        matches_with_stats >= 300
                        AND matches_with_odds >= 100
                        AND distinct_odds_markets >= 10
                    THEN 'STRONG'

                    WHEN
                        matches_with_stats >= 150
                        AND matches_with_odds >= 40
                        AND distinct_odds_markets >= 6
                    THEN 'USABLE'

                    WHEN
                        matches_with_stats >= 80
                        AND matches_with_odds >= 10
                    THEN 'WEAK_BUT_TESTABLE'

                    ELSE 'NOT_READY'
                END AS league_tier

            FROM league_base

            ORDER BY
                league_strength_score DESC,
                matches_with_odds DESC,
                odds_rows DESC

            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()

    missing_odds_priority = session.execute(
        text(
            """
            SELECT
                league,
                COUNT(*) AS matches_missing_odds
            FROM matches
            WHERE has_stats = true
              AND has_odds IS DISTINCT FROM true
              AND is_finished = true
            GROUP BY league
            ORDER BY matches_missing_odds DESC
            LIMIT 40
            """
        )
    ).mappings().all()

    return {
        "summary": dict(summary or {}),
        "leagues": [dict(row) for row in leagues],
        "missing_odds_priority": [dict(row) for row in missing_odds_priority],
    }