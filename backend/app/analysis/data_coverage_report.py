from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def build_data_coverage_report(session: Session) -> dict:
    summary = session.execute(
        text(
            """
            SELECT
                COUNT(*) AS total_matches,

                COUNT(*) FILTER (
                    WHERE is_finished = true
                ) AS finished_matches,

                COUNT(*) FILTER (
                    WHERE is_finished IS DISTINCT FROM true
                ) AS unfinished_matches,

                COUNT(*) FILTER (
                    WHERE has_stats = true
                ) AS matches_with_stats,

                COUNT(*) FILTER (
                    WHERE has_stats IS DISTINCT FROM true
                ) AS matches_missing_stats,

                COUNT(*) FILTER (
                    WHERE has_odds = true
                ) AS matches_with_odds,

                COUNT(*) FILTER (
                    WHERE has_odds IS DISTINCT FROM true
                ) AS matches_missing_odds

            FROM matches
            """
        )
    ).mappings().first()

    by_league = session.execute(
        text(
            """
            SELECT
                league,

                COUNT(*) AS total_matches,

                COUNT(*) FILTER (
                    WHERE has_stats = true
                ) AS with_stats,

                COUNT(*) FILTER (
                    WHERE has_stats IS DISTINCT FROM true
                ) AS missing_stats,

                COUNT(*) FILTER (
                    WHERE has_odds = true
                ) AS with_odds,

                COUNT(*) FILTER (
                    WHERE has_odds IS DISTINCT FROM true
                ) AS missing_odds,

                COUNT(*) FILTER (
                    WHERE is_finished = true
                ) AS finished_matches

            FROM matches

            GROUP BY league

            ORDER BY
                missing_stats DESC,
                missing_odds DESC,
                total_matches DESC

            LIMIT 30
            """
        )
    ).mappings().all()

    stats_rows = session.execute(
        text(
            """
            SELECT COUNT(*) AS total_stat_rows
            FROM team_match_stats
            """
        )
    ).scalar()

    update_priority = session.execute(
        text(
            """
            SELECT
                m.id AS match_id,
                m.provider_fixture_id,
                m.league,
                m.home_team,
                m.away_team,
                m.kickoff_date,

                m.has_stats,
                m.has_odds,

                m.stats_attempt_count,
                m.stats_unavailable,

                m.odds_attempt_count,
                m.odds_unavailable,

                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM team_match_stats s
                        WHERE s.match_id = m.id
                    )
                    THEN true
                    ELSE false
                END AS stats_rows_exist

            FROM matches m

            WHERE
                m.has_stats IS DISTINCT FROM true
                OR m.has_odds IS DISTINCT FROM true

            ORDER BY
                m.kickoff_date DESC NULLS LAST,
                m.id DESC

            LIMIT 100
            """
        )
    ).mappings().all()

    return {
        "summary": {
            **dict(summary or {}),
            "team_match_stats_rows": int(stats_rows or 0),
        },

        "by_league": [
            dict(row)
            for row in by_league
        ],

        "update_priority": [
            dict(row)
            for row in update_priority
        ],
    }