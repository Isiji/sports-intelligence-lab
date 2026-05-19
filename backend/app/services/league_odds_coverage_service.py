# backend/app/services/league_odds_coverage_service.py

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.db.models import LeagueOddsCoverageSnapshot


MIN_MATCHES_FOR_PRODUCTION = 5
MIN_ODDS_PENETRATION_RATE = 0.005
MIN_ODDS_SUCCESS_RATE = 0.10
MIN_ODDS_ATTEMPTED_MATCHES = 3
MIN_SUPPORTED_MARKETS = 2
MIN_BOOKMAKERS = 1

MIN_MARKET_DEPTH_SCORE = 0.05
MIN_BOOKMAKER_DEPTH_SCORE = 0.05

def rebuild_league_odds_coverage(
    session: Session,
    min_matches: int = MIN_MATCHES_FOR_PRODUCTION,
) -> dict:
    session.execute(
        delete(LeagueOddsCoverageSnapshot)
    )

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

                    COUNT(DISTINCT mo.market)
                        AS supported_market_count,

                    COUNT(DISTINCT mo.bookmaker) FILTER (
                        WHERE mo.bookmaker IS NOT NULL
                    ) AS bookmaker_count,

                    MAX(mo.retrieved_at)
                        AS last_odds_activity_at

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
                last_odds_activity_at,

                ROUND(
                    (
                        matches_with_odds::numeric
                        / NULLIF(total_matches, 0)
                    ),
                    4
                ) AS odds_coverage_rate,

                ROUND(
                    (
                        matches_with_odds::numeric
                        / NULLIF(odds_attempted_matches, 0)
                    ),
                    4
                ) AS odds_success_rate,
                
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

            ORDER BY
                matches_with_odds DESC,
                total_matches DESC
            """
        )
    ).mappings().all()

    inserted = 0
    production_allowed_count = 0
    production_blocked_count = 0

    priority_tier_distribution: dict[str, int] = {}

    for row in rows:
        total_matches = int(
            row["total_matches"] or 0
        )

        matches_with_odds = int(
            row["matches_with_odds"] or 0
        )

        odds_unavailable_matches = int(
            row["odds_unavailable_matches"] or 0
        )

        odds_attempted_matches = int(
            row["odds_attempted_matches"] or 0
        )

        total_odds_rows = int(
            row["total_odds_rows"] or 0
        )

        supported_market_count = int(
            row["supported_market_count"] or 0
        )

        bookmaker_count = int(
            row["bookmaker_count"] or 0
        )

        odds_coverage_rate = float(
            row["odds_coverage_rate"] or 0.0
        )
        odds_success_rate = float(
            row["odds_success_rate"] or 0.0
        )

        odds_unavailable_rate = float(
            row["odds_unavailable_rate"] or 0.0
        )

        avg_odds_rows_per_match = float(
            row["avg_odds_rows_per_match"] or 0.0
        )

        market_depth_score = calculate_market_depth_score(
            supported_market_count=supported_market_count,
            avg_odds_rows_per_match=avg_odds_rows_per_match,
        )

        bookmaker_depth_score = calculate_bookmaker_depth_score(
            bookmaker_count=bookmaker_count,
            avg_odds_rows_per_match=avg_odds_rows_per_match,
        )

        ecosystem_score = calculate_ecosystem_score(
            market_depth_score=market_depth_score,
            bookmaker_depth_score=bookmaker_depth_score,
            odds_coverage_rate=odds_coverage_rate,
            odds_success_rate=odds_success_rate,
            avg_odds_rows_per_match=avg_odds_rows_per_match,
        )

        coverage_score = calculate_coverage_score(
            total_matches=total_matches,
            matches_with_odds=matches_with_odds,
            odds_coverage_rate=odds_coverage_rate,
            odds_success_rate=odds_success_rate,
            odds_unavailable_rate=odds_unavailable_rate,
            supported_market_count=supported_market_count,
            bookmaker_count=bookmaker_count,
            avg_odds_rows_per_match=avg_odds_rows_per_match,
            ecosystem_score=ecosystem_score,
        )

        tier = resolve_coverage_tier(
            score=coverage_score,
            odds_coverage_rate=odds_coverage_rate,
            odds_success_rate=odds_success_rate,
            total_matches=total_matches,
            supported_market_count=supported_market_count,
            bookmaker_count=bookmaker_count,
        )        

        priority_tier = resolve_priority_tier(
            total_matches=total_matches,
            matches_with_odds=matches_with_odds,
            odds_coverage_rate=odds_coverage_rate,
            ecosystem_score=ecosystem_score,
            coverage_tier=tier,
        )

        (
            production_allowed,
            reason,
            ) = resolve_production_allowed(
                total_matches=total_matches,
                odds_coverage_rate=odds_coverage_rate,
                odds_success_rate=odds_success_rate,
                odds_attempted_matches=odds_attempted_matches,
                supported_market_count=supported_market_count,
                bookmaker_count=bookmaker_count,
                market_depth_score=market_depth_score,
                bookmaker_depth_score=bookmaker_depth_score,
                tier=tier,
                min_matches=min_matches,
            )
        if production_allowed:
            production_allowed_count += 1
        else:
            production_blocked_count += 1

        priority_tier_distribution[
            priority_tier
        ] = (
            priority_tier_distribution.get(
                priority_tier,
                0,
            )
            + 1
        )

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

                market_depth_score=market_depth_score,
                bookmaker_depth_score=bookmaker_depth_score,
                ecosystem_score=ecosystem_score,
                priority_tier=priority_tier,

                last_odds_activity_at=row[
                    "last_odds_activity_at"
                ],

                updated_at=datetime.utcnow(),
            )
        )

        inserted += 1

    session.commit()

    return {
        "league_odds_coverage_rows": inserted,
        "production_allowed": production_allowed_count,
        "production_blocked": production_blocked_count,
        "priority_tier_distribution": priority_tier_distribution,
    }


def calculate_market_depth_score(
    supported_market_count: int,
    avg_odds_rows_per_match: float,
) -> float:
    market_score = min(
        supported_market_count / 25.0,
        1.0,
    )

    density_score = min(
        avg_odds_rows_per_match / 800.0,
        1.0,
    )

    return round(
        (
            (market_score * 0.70)
            + (density_score * 0.30)
        ),
        4,
    )


def calculate_bookmaker_depth_score(
    bookmaker_count: int,
    avg_odds_rows_per_match: float,
) -> float:
    bookmaker_score = min(
        bookmaker_count / 12.0,
        1.0,
    )

    density_score = min(
        avg_odds_rows_per_match / 1000.0,
        1.0,
    )

    return round(
        (
            (bookmaker_score * 0.75)
            + (density_score * 0.25)
        ),
        4,
    )


def calculate_ecosystem_score(
    market_depth_score: float,
    bookmaker_depth_score: float,
    odds_coverage_rate: float,
    odds_success_rate: float,
    avg_odds_rows_per_match: float,
) -> float:
    ecosystem_density = min(
        avg_odds_rows_per_match / 1200.0,
        1.0,
    )

    return round(
        (
            (market_depth_score * 0.25)
            + (bookmaker_depth_score * 0.25)
            + (odds_coverage_rate * 0.15)
            + (odds_success_rate * 0.25)
            + (ecosystem_density * 0.10)
        )
        * 100.0,
        4,
    )

def calculate_coverage_score(
    total_matches: int,
    matches_with_odds: int,
    odds_coverage_rate: float,
    odds_success_rate: float,
    odds_unavailable_rate: float,
    supported_market_count: int,
    bookmaker_count: int,
    avg_odds_rows_per_match: float,
    ecosystem_score: float,
) -> float:
    sample_score = min(
        total_matches / 50.0,
        1.0,
    ) * 10.0

    penetration_score = min(
        odds_coverage_rate / 0.10,
        1.0,
    ) * 15.0

    success_score = (
        odds_success_rate * 25.0
    )

    availability_score = (
        max(
            1.0 - odds_unavailable_rate,
            0.0,
        )
        * 10.0
    )

    market_score = min(
        supported_market_count / 20.0,
        1.0,
    ) * 12.0

    bookmaker_score = min(
        bookmaker_count / 8.0,
        1.0,
    ) * 10.0

    density_score = min(
        avg_odds_rows_per_match / 600.0,
        1.0,
    ) * 8.0

    ecosystem_component = (
        ecosystem_score / 100.0
    ) * 10.0

    if matches_with_odds == 0:
        return 0.0

    return round(
        sample_score
        + penetration_score
        + success_score
        + availability_score
        + market_score
        + bookmaker_score
        + density_score
        + ecosystem_component,
        4,
    )

def resolve_coverage_tier(
    score: float,
    odds_coverage_rate: float,
    odds_success_rate: float,
    total_matches: int,
    supported_market_count: int,
    bookmaker_count: int,
) -> str:
    if total_matches < 5:
        return "INSUFFICIENT_SAMPLE"

    if odds_coverage_rate <= 0:
        return "NO_ODDS"

    if (
        score >= 85
        and odds_success_rate >= 0.85
        and supported_market_count >= 10
        and bookmaker_count >= 3
    ):
        return "ELITE_ODDS_COVERAGE"

    if (
        score >= 70
        and odds_success_rate >= 0.70
    ):
        return "STRONG_ODDS_COVERAGE"

    if (
        score >= 55
        and odds_success_rate >= 0.55
    ):
        return "USABLE_ODDS_COVERAGE"

    if (
        score >= 40
        and odds_success_rate >= 0.35
    ):
        return "LIMITED_ODDS_COVERAGE"

    return "POOR_ODDS_COVERAGE"


def resolve_priority_tier(
    total_matches: int,
    matches_with_odds: int,
    odds_coverage_rate: float,
    ecosystem_score: float,
    coverage_tier: str,
) -> str:

    if matches_with_odds <= 0:
        return "DISCOVERY_ROTATION"

    if (
        ecosystem_score >= 78
        and odds_coverage_rate >= 0.025
        and matches_with_odds >= 10
    ):
        return "CORE_PRODUCTION"

    if (
        ecosystem_score >= 65
        and odds_coverage_rate >= 0.015
        and matches_with_odds >= 6
    ):
        return "HIGH_PRIORITY"

    if (
        ecosystem_score >= 45
        and odds_coverage_rate >= 0.008
        and matches_with_odds >= 3
    ):
        return "GROWTH_PRIORITY"

    if (
        ecosystem_score >= 15
        and total_matches >= 20
    ):
        return "EXPLORATION_PRIORITY"

    return "DISCOVERY_ROTATION"

def resolve_production_allowed(
    total_matches: int,
    odds_coverage_rate: float,
    odds_success_rate: float,
    odds_attempted_matches: int,
    supported_market_count: int,
    bookmaker_count: int,
    market_depth_score: float,
    bookmaker_depth_score: float,
    tier: str,
    min_matches: int,
) -> tuple[bool, str]:

    if total_matches < min_matches:
        return (
            False,
            "insufficient_match_sample",
        )

    if matches_with_real_odds(
        odds_attempted_matches=odds_attempted_matches,
        supported_market_count=supported_market_count,
        bookmaker_count=bookmaker_count,
    ) is False:
        return (
            False,
            "weak_real_odds_ecosystem",
        )

    if tier in {
        "NO_ODDS",
        "INSUFFICIENT_SAMPLE",
    }:
        return (
            False,
            f"blocked_by_tier:{tier}",
        )

    if bookmaker_count < 1:
        return (
            False,
            "no_bookmaker_depth",
        )

    return (
        True,
        "production_allowed",
    )

def matches_with_real_odds(
    odds_attempted_matches: int,
    supported_market_count: int,
    bookmaker_count: int,
) -> bool:

    if odds_attempted_matches <= 0:
        return False

    if supported_market_count <= 0:
        return False

    if bookmaker_count <= 0:
        return False

    return True

def league_odds_coverage_report(
    session: Session,
    limit: int = 80,
    production_only: bool = False,
) -> dict:
    filters = []

    if production_only:
        filters.append(
            "production_allowed = true"
        )

    where_sql = ""

    if filters:
        where_sql = (
            "WHERE " + " AND ".join(filters)
        )

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

                market_depth_score,
                bookmaker_depth_score,
                ecosystem_score,

                coverage_score,
                coverage_tier,
                priority_tier,

                production_allowed,
                reason,

                last_odds_activity_at

            FROM league_odds_coverage_snapshots

            {where_sql}

            ORDER BY
                production_allowed DESC,
                ecosystem_score DESC,
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
                ) AS no_odds_leagues,

                COUNT(*) FILTER (
                    WHERE priority_tier = 'CORE_PRODUCTION'
                ) AS core_production_leagues,

                COUNT(*) FILTER (
                    WHERE priority_tier = 'HIGH_PRIORITY'
                ) AS high_priority_leagues,

                COUNT(*) FILTER (
                    WHERE priority_tier = 'GROWTH_PRIORITY'
                ) AS growth_priority_leagues,

                COUNT(*) FILTER (
                    WHERE priority_tier = 'EXPLORATION_PRIORITY'
                ) AS exploration_priority_leagues,

                COUNT(*) FILTER (
                    WHERE priority_tier = 'DISCOVERY_ROTATION'
                ) AS discovery_rotation_leagues

            FROM league_odds_coverage_snapshots
            """
        )
    ).mappings().first()

    return {
        "summary": dict(summary or {}),
        "leagues": [
            dict(row)
            for row in rows
        ],
    }