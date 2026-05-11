# backend/app/services/league_odds_coverage_service.py

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.db.models import LeagueOddsCoverageSnapshot


MIN_MATCHES_FOR_PRODUCTION = 10
MIN_ODDS_COVERAGE_RATE = 0.35
MIN_SUPPORTED_MARKETS = 3
MIN_BOOKMAKERS = 1


def rebuild_league_odds_coverage(
    session: Session,
    min_matches: int = MIN_MATCHES_FOR_PRODUCTION,
) -> dict:
    session.execute(delete(LeagueOddsCoverageSnapshot))

    rows = session.execute(
        text(
            """
            WITH odds_summary AS (
                SELECT
                    m.league,
                    COUNT(DISTINCT m.id) AS total_matches,

                    COUNT(DISTINCT m.id) FILTER (
                        WHERE m.has_odds = true
                    ) AS matches_with_odds,

                    COUNT(DISTINCT m.id) FILTER (
                        WHERE m.odds_unavailable = true
                    ) AS odds_unavailable_matches,

                    COUNT(DISTINCT m.id) FILTER (
                        WHERE m.odds_attempt_count > 0
                    ) AS odds_attempted_matches,

                    COUNT(mo.id) AS total_odds_rows,

                    COUNT(DISTINCT mo.market) AS supported_market_count,

                    COUNT(DISTINCT mo.bookmaker) FILTER (
                        WHERE mo.bookmaker IS NOT NULL
                    ) AS bookmaker_count

                FROM matches m

                LEFT JOIN match_odds mo
                    ON mo.match_id = m.id

                WHERE m.sport = 'football'
                  AND m.provider = 'api-football'
                  AND m.league IS NOT NULL

                GROUP BY m.league
            )

            SELECT
                league,
                total_matches,
                matches_with_odds,
                odds_unavailable_matches,
                odds_attempted_matches,
                total_odds_rows,
                supported_market_count,
                bookmaker_count,

                ROUND(
                    (
                        matches_with_odds::numeric
                        / NULLIF(total_matches, 0)
                    ),
                    4
                ) AS odds_coverage_rate,

                ROUND(
                    (
                        odds_unavailable_matches::numeric
                        / NULLIF(
                            CASE
                                WHEN odds_attempted_matches > 0
                                THEN odds_attempted_matches
                                ELSE total_matches
                            END,
                            0
                        )
                    ),
                    4
                ) AS odds_unavailable_rate,

                ROUND(
                    (
                        total_odds_rows::numeric
                        / NULLIF(matches_with_odds, 0)
                    ),
                    4
                ) AS avg_odds_rows_per_match

            FROM odds_summary

            ORDER BY matches_with_odds DESC, total_matches DESC
            """
        )
    ).mappings().all()

    inserted = 0
    allowed = 0
    blocked = 0

    for row in rows:
        total_matches = int(row["total_matches"] or 0)
        matches_with_odds = int(row["matches_with_odds"] or 0)
        odds_unavailable_matches = int(row["odds_unavailable_matches"] or 0)
        odds_attempted_matches = int(row["odds_attempted_matches"] or 0)
        total_odds_rows = int(row["total_odds_rows"] or 0)
        supported_market_count = int(row["supported_market_count"] or 0)
        bookmaker_count = int(row["bookmaker_count"] or 0)

        odds_coverage_rate = float(row["odds_coverage_rate"] or 0.0)
        odds_unavailable_rate = float(row["odds_unavailable_rate"] or 0.0)
        avg_odds_rows_per_match = float(row["avg_odds_rows_per_match"] or 0.0)

        coverage_score = calculate_coverage_score(
            total_matches=total_matches,
            matches_with_odds=matches_with_odds,
            odds_coverage_rate=odds_coverage_rate,
            odds_unavailable_rate=odds_unavailable_rate,
            supported_market_count=supported_market_count,
            bookmaker_count=bookmaker_count,
            avg_odds_rows_per_match=avg_odds_rows_per_match,
        )

        tier = resolve_coverage_tier(
            score=coverage_score,
            odds_coverage_rate=odds_coverage_rate,
            total_matches=total_matches,
            supported_market_count=supported_market_count,
        )

        production_allowed, reason = resolve_production_allowed(
            total_matches=total_matches,
            odds_coverage_rate=odds_coverage_rate,
            supported_market_count=supported_market_count,
            bookmaker_count=bookmaker_count,
            tier=tier,
            min_matches=min_matches,
        )

        if production_allowed:
            allowed += 1
        else:
            blocked += 1

        session.add(
            LeagueOddsCoverageSnapshot(
                sport="football",
                league=row["league"],
                total_matches=total_matches,
                matches_with_odds=matches_with_odds,
                odds_unavailable_matches=odds_unavailable_matches,
                odds_attempted_matches=odds_attempted_matches,
                odds_coverage_rate=odds_coverage_rate,
                odds_unavailable_rate=odds_unavailable_rate,
                total_odds_rows=total_odds_rows,
                avg_odds_rows_per_match=avg_odds_rows_per_match,
                supported_market_count=supported_market_count,
                bookmaker_count=bookmaker_count,
                coverage_score=coverage_score,
                coverage_tier=tier,
                production_allowed=production_allowed,
                reason=reason,
                updated_at=datetime.utcnow(),
            )
        )

        inserted += 1

    session.commit()

    return {
        "league_odds_coverage_rows": inserted,
        "production_allowed": allowed,
        "production_blocked": blocked,
    }


def calculate_coverage_score(
    total_matches: int,
    matches_with_odds: int,
    odds_coverage_rate: float,
    odds_unavailable_rate: float,
    supported_market_count: int,
    bookmaker_count: int,
    avg_odds_rows_per_match: float,
) -> float:
    sample_score = min(total_matches / 50.0, 1.0) * 20.0
    coverage_score = odds_coverage_rate * 35.0
    availability_score = max(1.0 - odds_unavailable_rate, 0.0) * 15.0
    market_score = min(supported_market_count / 12.0, 1.0) * 15.0
    bookmaker_score = min(bookmaker_count / 5.0, 1.0) * 10.0
    depth_score = min(avg_odds_rows_per_match / 250.0, 1.0) * 5.0

    if matches_with_odds == 0:
        return 0.0

    return round(
        sample_score
        + coverage_score
        + availability_score
        + market_score
        + bookmaker_score
        + depth_score,
        4,
    )


def resolve_coverage_tier(
    score: float,
    odds_coverage_rate: float,
    total_matches: int,
    supported_market_count: int,
) -> str:
    if total_matches < 5:
        return "INSUFFICIENT_SAMPLE"

    if odds_coverage_rate <= 0:
        return "NO_ODDS"

    if score >= 75 and odds_coverage_rate >= 0.75:
        return "ELITE_ODDS_COVERAGE"

    if score >= 60 and odds_coverage_rate >= 0.55:
        return "STRONG_ODDS_COVERAGE"

    if score >= 42 and odds_coverage_rate >= 0.35:
        return "USABLE_ODDS_COVERAGE"

    if supported_market_count >= 3 and odds_coverage_rate >= 0.20:
        return "LIMITED_ODDS_COVERAGE"

    return "POOR_ODDS_COVERAGE"


def resolve_production_allowed(
    total_matches: int,
    odds_coverage_rate: float,
    supported_market_count: int,
    bookmaker_count: int,
    tier: str,
    min_matches: int,
) -> tuple[bool, str]:
    if total_matches < min_matches:
        return False, "insufficient_match_sample"

    if tier in {
        "NO_ODDS",
        "POOR_ODDS_COVERAGE",
        "INSUFFICIENT_SAMPLE",
    }:
        return False, f"blocked_by_tier:{tier}"

    if odds_coverage_rate < MIN_ODDS_COVERAGE_RATE:
        return False, "odds_coverage_rate_too_low"

    if supported_market_count < MIN_SUPPORTED_MARKETS:
        return False, "not_enough_supported_markets"

    if bookmaker_count < MIN_BOOKMAKERS:
        return False, "no_bookmaker_depth"

    return True, "production_allowed"


def league_odds_coverage_report(
    session: Session,
    limit: int = 80,
    production_only: bool = False,
) -> dict:
    filters = []

    if production_only:
        filters.append("production_allowed = true")

    where_sql = ""
    if filters:
        where_sql = "WHERE " + " AND ".join(filters)

    rows = session.execute(
        text(
            f"""
            SELECT
                league,
                total_matches,
                matches_with_odds,
                odds_unavailable_matches,
                odds_attempted_matches,
                odds_coverage_rate,
                odds_unavailable_rate,
                total_odds_rows,
                avg_odds_rows_per_match,
                supported_market_count,
                bookmaker_count,
                coverage_score,
                coverage_tier,
                production_allowed,
                reason
            FROM league_odds_coverage_snapshots
            {where_sql}
            ORDER BY
                production_allowed DESC,
                coverage_score DESC,
                matches_with_odds DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()

    summary = session.execute(
        text(
            """
            SELECT
                COUNT(*) AS leagues,
                COUNT(*) FILTER (
                    WHERE production_allowed = true
                ) AS production_allowed_leagues,

                COUNT(*) FILTER (
                    WHERE coverage_tier = 'ELITE_ODDS_COVERAGE'
                ) AS elite_leagues,

                COUNT(*) FILTER (
                    WHERE coverage_tier = 'STRONG_ODDS_COVERAGE'
                ) AS strong_leagues,

                COUNT(*) FILTER (
                    WHERE coverage_tier = 'USABLE_ODDS_COVERAGE'
                ) AS usable_leagues,

                COUNT(*) FILTER (
                    WHERE coverage_tier = 'LIMITED_ODDS_COVERAGE'
                ) AS limited_leagues,

                COUNT(*) FILTER (
                    WHERE coverage_tier = 'POOR_ODDS_COVERAGE'
                ) AS poor_leagues,

                COUNT(*) FILTER (
                    WHERE coverage_tier = 'NO_ODDS'
                ) AS no_odds_leagues
            FROM league_odds_coverage_snapshots
            """
        )
    ).mappings().first()

    return {
        "summary": dict(summary or {}),
        "leagues": [dict(row) for row in rows],
    }