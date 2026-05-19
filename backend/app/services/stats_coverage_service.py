# backend/app/services/stats_coverage_service.py

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def rebuild_stats_coverage(session: Session) -> dict[str, Any]:
    rows = session.execute(
        text(
            """
            SELECT
                m.league,
                m.season,
                COUNT(*) FILTER (WHERE m.is_finished = true) AS finished_matches,
                COUNT(*) FILTER (WHERE m.has_stats = true) AS matches_with_stats,
                COUNT(*) FILTER (WHERE m.stats_unavailable = true) AS stats_unavailable_matches,
                COUNT(*) FILTER (WHERE m.stats_attempt_count > 0) AS stats_attempted_matches,
                COUNT(DISTINCT tms.match_id) FILTER (WHERE tms.is_real = true) AS matches_with_real_stats
            FROM matches m
            LEFT JOIN team_match_stats tms ON tms.match_id = m.id
            WHERE m.provider = 'api-football'
              AND m.league IS NOT NULL
              AND m.is_cancelled = false
              AND m.is_postponed = false
            GROUP BY m.league, m.season
            ORDER BY matches_with_real_stats DESC, finished_matches DESC
            """
        )
    ).mappings().all()

    results = []

    for row in rows:
        finished = int(row["finished_matches"] or 0)
        with_stats = int(row["matches_with_stats"] or 0)
        real_stats = int(row["matches_with_real_stats"] or 0)
        unavailable = int(row["stats_unavailable_matches"] or 0)
        attempted = int(row["stats_attempted_matches"] or 0)

        coverage_rate = round(real_stats / finished, 4) if finished else 0.0
        success_rate = round(real_stats / attempted, 4) if attempted else 0.0
        unavailable_rate = round(unavailable / attempted, 4) if attempted else 0.0

        score = round(
            coverage_rate * 0.45
            + success_rate * 0.40
            + max(0.0, 1.0 - unavailable_rate) * 0.15,
            4,
        )

        if score >= 0.70:
            tier = "STRONG_STATS_COVERAGE"
        elif score >= 0.45:
            tier = "USABLE_STATS_COVERAGE"
        elif score >= 0.20:
            tier = "LIMITED_STATS_COVERAGE"
        else:
            tier = "POOR_STATS_COVERAGE"

        production_allowed = tier in {
            "STRONG_STATS_COVERAGE",
            "USABLE_STATS_COVERAGE",
        }

        results.append(
            {
                "league": row["league"],
                "season": row["season"],
                "finished_matches": finished,
                "matches_with_stats": with_stats,
                "matches_with_real_stats": real_stats,
                "stats_unavailable_matches": unavailable,
                "stats_attempted_matches": attempted,
                "stats_coverage_rate": coverage_rate,
                "stats_success_rate": success_rate,
                "stats_unavailable_rate": unavailable_rate,
                "coverage_score": score,
                "coverage_tier": tier,
                "production_allowed": production_allowed,
                "updated_at": datetime.utcnow().isoformat(),
            }
        )

    return {
        "stats_coverage_rows": len(results),
        "production_allowed": sum(1 for row in results if row["production_allowed"]),
        "production_blocked": sum(1 for row in results if not row["production_allowed"]),
        "rows": results[:100],
    }


def stats_coverage_report(
    session: Session,
    season: int | None = None,
    limit: int = 80,
) -> dict[str, Any]:
    filters = ""

    params: dict[str, Any] = {
        "limit": limit,
    }

    if season is not None:
        filters = "AND m.season = :season"
        params["season"] = season

    rows = session.execute(
        text(
            f"""
            SELECT
                m.league,
                m.season,
                COUNT(*) FILTER (WHERE m.is_finished = true) AS finished_matches,
                COUNT(*) FILTER (WHERE m.has_stats = true) AS matches_with_stats,
                COUNT(*) FILTER (WHERE m.stats_unavailable = true) AS stats_unavailable_matches,
                COUNT(*) FILTER (WHERE m.stats_attempt_count > 0) AS stats_attempted_matches,
                COUNT(DISTINCT tms.match_id) FILTER (WHERE tms.is_real = true) AS matches_with_real_stats
            FROM matches m
            LEFT JOIN team_match_stats tms ON tms.match_id = m.id
            WHERE m.provider = 'api-football'
              AND m.league IS NOT NULL
              AND m.is_cancelled = false
              AND m.is_postponed = false
              {filters}
            GROUP BY m.league, m.season
            ORDER BY matches_with_real_stats DESC, finished_matches DESC
            LIMIT :limit
            """
        ),
        params,
    ).mappings().all()

    report_rows = []

    for row in rows:
        finished = int(row["finished_matches"] or 0)
        real_stats = int(row["matches_with_real_stats"] or 0)
        attempted = int(row["stats_attempted_matches"] or 0)
        unavailable = int(row["stats_unavailable_matches"] or 0)

        report_rows.append(
            {
                "league": row["league"],
                "season": row["season"],
                "finished_matches": finished,
                "matches_with_real_stats": real_stats,
                "stats_attempted_matches": attempted,
                "stats_unavailable_matches": unavailable,
                "stats_coverage_rate": round(real_stats / finished, 4) if finished else 0.0,
                "stats_success_rate": round(real_stats / attempted, 4) if attempted else 0.0,
                "stats_unavailable_rate": round(unavailable / attempted, 4) if attempted else 0.0,
            }
        )

    return {
        "season": season,
        "rows": report_rows,
    }