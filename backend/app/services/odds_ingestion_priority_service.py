# backend/app/services/odds_ingestion_priority_service.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session


OddsIngestionMode = Literal[
    "priority",
    "rotation",
    "rich_leagues",
    "all_leagues_rotation",
]


@dataclass(frozen=True)
class OddsIngestionCandidate:
    match_id: int
    provider_fixture_id: str | None
    league: str | None
    season: int | None
    kickoff_date: date | None
    is_finished: bool
    has_odds: bool
    odds_unavailable: bool
    odds_attempt_count: int
    priority_score: float
    priority_reason: str


class OddsIngestionPriorityService:
    """
    Production-safe odds ingestion prioritizer.

    Strategy:
    - Prioritize leagues/matches likely to return odds.
    - Avoid repeated waste on fixtures already marked unavailable.
    - Still rotate into every league over time.
    - Low priority means delayed, not excluded.
    """

    def __init__(self, session: Session):
        self.session = session

    def get_candidates(
        self,
        *,
        mode: OddsIngestionMode = "priority",
        limit: int = 300,
        max_attempts: int = 3,
        include_finished: bool = True,
        include_upcoming: bool = True,
        upcoming_days: int = 14,
        rotation_offset: int = 0,
    ) -> list[OddsIngestionCandidate]:
        today = date.today()
        max_upcoming_date = today + timedelta(days=upcoming_days)

        rows = self.session.execute(
            text(
                """
                WITH coverage AS (
                    SELECT
                        league,
                        production_allowed,
                        priority_tier,
                        ecosystem_score,
                        market_depth_score,
                        bookmaker_depth_score,
                        odds_coverage_rate,
                        odds_success_rate,
                        last_odds_activity_at
                    FROM league_odds_coverage_snapshots
                ),

                candidate_base AS (
                    SELECT
                        m.id AS match_id,
                        m.provider_fixture_id,
                        m.league,
                        m.season,
                        m.kickoff_date,
                        m.is_finished,

                        COALESCE(m.has_odds, false) AS has_odds,
                        COALESCE(m.odds_unavailable, false) AS odds_unavailable,
                        COALESCE(m.odds_attempt_count, 0) AS odds_attempt_count,

                        COALESCE(c.production_allowed, false)
                            AS production_allowed,

                        COALESCE(
                            c.priority_tier,
                            'DISCOVERY_ROTATION'
                        ) AS priority_tier,

                        COALESCE(c.ecosystem_score, 0)
                            AS ecosystem_score,

                        COALESCE(c.market_depth_score, 0)
                            AS market_depth_score,

                        COALESCE(c.bookmaker_depth_score, 0)
                            AS bookmaker_depth_score,

                        COALESCE(c.odds_coverage_rate, 0)
                            AS odds_coverage_rate,

                        COALESCE(c.odds_success_rate, 0)
                            AS odds_success_rate,

                        c.last_odds_activity_at

                    FROM matches m

                    LEFT JOIN coverage c
                        ON c.league = m.league

                    WHERE
                        m.provider_fixture_id IS NOT NULL

                        AND COALESCE(m.has_odds, false) = false

                        AND COALESCE(
                            m.odds_attempt_count,
                            0
                        ) < :max_attempts

                        AND (
                            COALESCE(
                                m.odds_unavailable,
                                false
                            ) = false

                            OR

                            COALESCE(
                                m.odds_attempt_count,
                                0
                            ) = 0
                        )

                        AND (
                            (
                                :include_upcoming = true
                                AND m.kickoff_date BETWEEN :today AND :max_upcoming_date
                            )

                            OR

                            (
                                :include_finished = true
                                AND m.is_finished = true
                            )
                        )
                ),

                scored AS (
                    SELECT
                        *,

                        (
                            CASE
                                WHEN production_allowed = true
                                    THEN 120
                                ELSE 0
                            END

                            +

                            CASE
                                WHEN priority_tier = 'CORE_PRODUCTION'
                                    THEN 100

                                WHEN priority_tier = 'HIGH_PRIORITY'
                                    THEN 70

                                WHEN priority_tier = 'GROWTH_PRIORITY'
                                    THEN 45

                                WHEN priority_tier = 'EXPLORATION_PRIORITY'
                                    THEN 20

                                ELSE 0
                            END

                            +

                            (
                                ecosystem_score * 0.60
                            )

                            +

                            (
                                odds_success_rate * 50
                            )

                            +

                            (
                                market_depth_score * 20
                            )

                            +

                            (
                                bookmaker_depth_score * 20
                            )

                            +

                            CASE
                                WHEN kickoff_date BETWEEN :today AND :max_upcoming_date
                                    THEN 35
                                ELSE 0
                            END

                            +

                            CASE
                                WHEN is_finished = true
                                    THEN 12
                                ELSE 0
                            END

                            +

                            CASE
                                WHEN odds_attempt_count = 0
                                    THEN 20
                                WHEN odds_attempt_count = 1
                                    THEN 10
                                ELSE 0
                            END

                            +

                            CASE
                                WHEN last_odds_activity_at >= NOW() - INTERVAL '3 days'
                                    THEN 15
                                WHEN last_odds_activity_at >= NOW() - INTERVAL '7 days'
                                    THEN 8
                                ELSE 0
                            END

                            -

                            (
                                odds_attempt_count * 18
                            )

                            -

                            CASE
                                WHEN odds_unavailable = true
                                    THEN 40
                                ELSE 0
                            END

                        ) AS base_priority_score

                    FROM candidate_base
                )

                SELECT
                    match_id,
                    provider_fixture_id,
                    league,
                    season,
                    kickoff_date,
                    is_finished,
                    has_odds,
                    odds_unavailable,
                    odds_attempt_count,

                    CASE
                        WHEN :mode = 'rich_leagues'
                            THEN base_priority_score
                                + CASE
                                    WHEN priority_tier IN (
                                        'CORE_PRODUCTION',
                                        'HIGH_PRIORITY'
                                    )
                                    THEN 50
                                    ELSE -25
                                END

                        WHEN :mode = 'rotation'
                            THEN base_priority_score
                                + MOD(
                                    match_id + :rotation_offset,
                                    17
                                )

                        WHEN :mode = 'all_leagues_rotation'
                            THEN base_priority_score
                                + CASE
                                    WHEN priority_tier = 'DISCOVERY_ROTATION'
                                    THEN 35
                                    ELSE 0
                                END
                                + MOD(
                                    match_id + :rotation_offset,
                                    29
                                )

                        ELSE base_priority_score
                    END AS priority_score,

                    CASE
                        WHEN production_allowed = true
                            THEN 'production_allowed_league'

                        WHEN priority_tier = 'CORE_PRODUCTION'
                            THEN 'core_production_growth'

                        WHEN priority_tier = 'HIGH_PRIORITY'
                            THEN 'high_priority_growth'

                        WHEN priority_tier = 'GROWTH_PRIORITY'
                            THEN 'growth_priority_expansion'

                        WHEN priority_tier = 'EXPLORATION_PRIORITY'
                            THEN 'ecosystem_exploration'

                        ELSE 'discovery_rotation'
                    END AS priority_reason

                FROM scored

                ORDER BY
                    priority_score DESC,
                    kickoff_date ASC NULLS LAST,
                    match_id ASC

                LIMIT :limit
                """
            ),
            {
                "mode": mode,
                "limit": limit,
                "max_attempts": max_attempts,
                "include_finished": include_finished,
                "include_upcoming": include_upcoming,
                "today": today,
                "max_upcoming_date": max_upcoming_date,
                "rotation_offset": rotation_offset,
            },
        ).mappings().all()

        return [
            OddsIngestionCandidate(
                match_id=row["match_id"],
                provider_fixture_id=row["provider_fixture_id"],
                league=row["league"],
                season=row["season"],
                kickoff_date=row["kickoff_date"],
                is_finished=bool(row["is_finished"]),
                has_odds=bool(row["has_odds"]),
                odds_unavailable=bool(row["odds_unavailable"]),
                odds_attempt_count=int(row["odds_attempt_count"] or 0),
                priority_score=float(row["priority_score"] or 0),
                priority_reason=row["priority_reason"],
            )
            for row in rows
        ]

    def coverage_summary(self) -> dict:
        row = self.session.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_matches,
                    COUNT(*) FILTER (WHERE has_odds = true) AS matches_with_odds,
                    COUNT(DISTINCT league) AS total_leagues,
                    COUNT(DISTINCT league) FILTER (WHERE has_odds = true) AS leagues_with_odds,
                    COUNT(*) FILTER (
                        WHERE COALESCE(odds_attempt_count, 0) > 0
                    ) AS matches_attempted_for_odds,
                    COUNT(*) FILTER (
                        WHERE COALESCE(odds_unavailable, false) = true
                    ) AS matches_marked_odds_unavailable
                FROM matches
                """
            )
        ).mappings().first()

        return dict(row or {})

    def league_priority_report(self, *, limit: int = 50) -> list[dict]:
        rows = self.session.execute(
            text(
                """
                SELECT
                    league,
                    COUNT(*) AS total_matches,
                    COUNT(*) FILTER (WHERE has_odds = true) AS matches_with_odds,
                    COUNT(*) FILTER (WHERE has_stats = true) AS matches_with_stats,
                    COUNT(*) FILTER (
                        WHERE COALESCE(odds_attempt_count, 0) > 0
                    ) AS odds_attempted,
                    COUNT(*) FILTER (
                        WHERE COALESCE(odds_unavailable, false) = true
                    ) AS odds_unavailable,
                    ROUND(
                        COUNT(*) FILTER (WHERE has_odds = true)::numeric
                        / NULLIF(COUNT(*), 0),
                        4
                    ) AS odds_coverage_ratio,
                    ROUND(
                        COUNT(*) FILTER (WHERE has_stats = true)::numeric
                        / NULLIF(COUNT(*), 0),
                        4
                    ) AS stats_coverage_ratio
                FROM matches
                WHERE league IS NOT NULL
                GROUP BY league
                ORDER BY
                    COUNT(*) FILTER (WHERE has_odds = true) DESC,
                    COUNT(*) FILTER (WHERE has_stats = true) DESC,
                    COUNT(*) DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()

        return [dict(row) for row in rows]