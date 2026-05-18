# backend/app/services/league_market_coverage_service.py

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.db.models import LeagueMarketCoverageSnapshot
from app.odds.executable_market_registry import is_production_ready_market


MIN_MATCHES_WITH_MARKET = 3
MIN_BOOKMAKERS = 2
MIN_MARKET_COVERAGE_RATE = 0.03


def rebuild_league_market_coverage(session: Session) -> dict:
    session.execute(delete(LeagueMarketCoverageSnapshot))

    rows = session.execute(
        text(
            """
            WITH league_totals AS (
                SELECT
                    league,
                    COUNT(DISTINCT id) AS total_league_matches
                FROM matches
                WHERE sport = 'football'
                  AND provider = 'api-football'
                  AND league IS NOT NULL
                GROUP BY league
            ),
            market_rows AS (
                SELECT
                    m.league,
                    mo.market,
                    COUNT(DISTINCT mo.match_id) AS matches_with_market,
                    COUNT(*) AS total_market_rows,
                    COUNT(DISTINCT mo.bookmaker) FILTER (
                        WHERE mo.bookmaker IS NOT NULL
                    ) AS bookmaker_count
                FROM match_odds mo
                JOIN matches m
                    ON m.id = mo.match_id
                WHERE m.sport = 'football'
                  AND m.provider = 'api-football'
                  AND m.league IS NOT NULL
                  AND mo.market IS NOT NULL
                GROUP BY m.league, mo.market
            )
            SELECT
                mr.league,
                mr.market,
                lt.total_league_matches,
                mr.matches_with_market,
                mr.total_market_rows,
                mr.bookmaker_count,
                ROUND(
                    mr.matches_with_market::numeric
                    / NULLIF(lt.total_league_matches, 0),
                    4
                ) AS market_coverage_rate,
                ROUND(
                    mr.total_market_rows::numeric
                    / NULLIF(mr.matches_with_market, 0),
                    4
                ) AS avg_rows_per_match
            FROM market_rows mr
            JOIN league_totals lt
                ON lt.league = mr.league
            """
        )
    ).mappings().all()

    inserted = 0
    allowed = 0
    blocked = 0

    for row in rows:
        market = str(row["market"])

        matches_with_market = int(row["matches_with_market"] or 0)
        bookmaker_count = int(row["bookmaker_count"] or 0)
        market_coverage_rate = float(row["market_coverage_rate"] or 0.0)
        avg_rows_per_match = float(row["avg_rows_per_match"] or 0.0)
        total_market_rows = int(row["total_market_rows"] or 0)

        score = calculate_market_quality_score(
            matches_with_market=matches_with_market,
            market_coverage_rate=market_coverage_rate,
            bookmaker_count=bookmaker_count,
            avg_rows_per_match=avg_rows_per_match,
        )

        tier = resolve_market_tier(
            score=score,
            matches_with_market=matches_with_market,
            bookmaker_count=bookmaker_count,
        )

        production_allowed, reason = resolve_production_allowed(
            market=market,
            tier=tier,
            matches_with_market=matches_with_market,
            market_coverage_rate=market_coverage_rate,
            bookmaker_count=bookmaker_count,
        )

        if production_allowed:
            allowed += 1
        else:
            blocked += 1

        session.add(
            LeagueMarketCoverageSnapshot(
                sport="football",
                league=row["league"],
                market=market,
                matches_with_market=matches_with_market,
                total_market_rows=total_market_rows,
                bookmaker_count=bookmaker_count,
                market_coverage_rate=market_coverage_rate,
                avg_rows_per_match=avg_rows_per_match,
                market_quality_score=score,
                market_tier=tier,
                production_allowed=production_allowed,
                reason=reason,
                updated_at=datetime.utcnow(),
            )
        )

        inserted += 1

    session.commit()

    return {
        "league_market_coverage_rows": inserted,
        "production_allowed": allowed,
        "production_blocked": blocked,
    }


def calculate_market_quality_score(
    matches_with_market: int,
    market_coverage_rate: float,
    bookmaker_count: int,
    avg_rows_per_match: float,
) -> float:
    return round(
        min(matches_with_market / 20.0, 1.0) * 30.0
        + min(market_coverage_rate / 0.10, 1.0) * 25.0
        + min(bookmaker_count / 8.0, 1.0) * 25.0
        + min(avg_rows_per_match / 100.0, 1.0) * 20.0,
        4,
    )


def resolve_market_tier(
    score: float,
    matches_with_market: int,
    bookmaker_count: int,
) -> str:
    if matches_with_market < MIN_MATCHES_WITH_MARKET:
        return "INSUFFICIENT_SAMPLE"

    if bookmaker_count <= 0:
        return "NO_BOOKMAKER_DEPTH"

    if score >= 75:
        return "ELITE_MARKET_COVERAGE"

    if score >= 60:
        return "STRONG_MARKET_COVERAGE"

    if score >= 40:
        return "USABLE_MARKET_COVERAGE"

    if score >= 25:
        return "LIMITED_MARKET_COVERAGE"

    return "POOR_MARKET_COVERAGE"


def resolve_production_allowed(
    *,
    market: str,
    tier: str,
    matches_with_market: int,
    market_coverage_rate: float,
    bookmaker_count: int,
) -> tuple[bool, str]:
    if not is_production_ready_market(market):
        return False, "market_not_production_ready"

    if matches_with_market < MIN_MATCHES_WITH_MARKET:
        return False, "insufficient_market_sample"

    if bookmaker_count < MIN_BOOKMAKERS:
        return False, "insufficient_bookmaker_depth"

    if market_coverage_rate < MIN_MARKET_COVERAGE_RATE:
        return False, "market_coverage_too_low"

    if tier in {
        "ELITE_MARKET_COVERAGE",
        "STRONG_MARKET_COVERAGE",
        "USABLE_MARKET_COVERAGE",
    }:
        return True, "production_allowed"

    return False, f"blocked_by_tier:{tier}"


def league_market_coverage_report(
    session: Session,
    limit: int = 100,
    production_only: bool = False,
) -> dict:
    where_sql = "WHERE production_allowed = true" if production_only else ""

    rows = session.execute(
        text(
            f"""
            SELECT *
            FROM league_market_coverage_snapshots
            {where_sql}
            ORDER BY
                production_allowed DESC,
                market_quality_score DESC,
                matches_with_market DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()

    return {
        "rows": [dict(row) for row in rows]
    }