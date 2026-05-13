# backend/app/services/orchestration_telemetry_service.py

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class OrchestrationTelemetryService:
    """
    Production-safe orchestration telemetry.

    Tracks:
    - API calls
    - odds ingestion efficiency
    - stats ingestion efficiency
    - skipped/wasted calls
    - league-level waste
    - provider sync performance

    Uses existing tables:
    - matches
    - match_odds
    - team_match_stats
    - provider_sync_logs
    - api_call_logs
    """

    def __init__(self, session: Session):
        self.session = session

    def build_report(self, days: int = 1) -> dict[str, Any]:
        since = datetime.utcnow() - timedelta(days=days)

        return {
            "window_days": days,
            "generated_at": datetime.utcnow().isoformat(),
            "api_usage": self.api_usage_since(since),
            "odds_ingestion": self.odds_ingestion_since(since),
            "stats_ingestion": self.stats_ingestion_since(since),
            "provider_sync": self.provider_sync_since(since),
            "league_waste": self.league_waste_since(since),
            "finished_match_waste": self.finished_match_waste_since(since),
            "upcoming_match_waste": self.upcoming_match_waste_since(since),
        }

    def api_usage_since(self, since: datetime) -> dict[str, Any]:
        row = self.session.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_calls,
                    COUNT(*) FILTER (WHERE provider = 'api-football') AS api_football_calls
                FROM api_call_logs
                WHERE called_at >= :since
                """
            ),
            {"since": since},
        ).mappings().first()

        return {
            "total_calls": int(row["total_calls"] or 0),
            "api_football_calls": int(row["api_football_calls"] or 0),
        }

    def provider_sync_since(self, since: datetime) -> dict[str, Any]:
        rows = self.session.execute(
            text(
                """
                SELECT
                    sync_type,
                    status,
                    COUNT(*) AS runs,
                    COALESCE(SUM(records_received), 0) AS records_received,
                    COALESCE(SUM(records_inserted), 0) AS records_inserted,
                    COALESCE(SUM(records_updated), 0) AS records_updated,
                    COALESCE(SUM(records_skipped), 0) AS records_skipped
                FROM provider_sync_logs
                WHERE started_at >= :since
                GROUP BY sync_type, status
                ORDER BY sync_type, status
                """
            ),
            {"since": since},
        ).mappings().all()

        return [dict(row) for row in rows]

    def odds_ingestion_since(self, since: datetime) -> dict[str, Any]:
        row = self.session.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE odds_attempted_at >= :since
                    ) AS matches_attempted,

                    COUNT(*) FILTER (
                        WHERE odds_attempted_at >= :since
                        AND has_odds = TRUE
                    ) AS matches_with_odds,

                    COUNT(*) FILTER (
                        WHERE odds_attempted_at >= :since
                        AND odds_unavailable = TRUE
                    ) AS matches_marked_unavailable,

                    COUNT(*) FILTER (
                        WHERE odds_attempted_at >= :since
                        AND is_finished = TRUE
                    ) AS finished_attempts,

                    COUNT(*) FILTER (
                        WHERE odds_attempted_at >= :since
                        AND is_finished = FALSE
                    ) AS upcoming_attempts,

                    COUNT(*) FILTER (
                        WHERE odds_attempted_at >= :since
                        AND odds_attempt_count >= 3
                        AND has_odds = FALSE
                    ) AS exhausted_without_odds
                FROM matches
                """
            ),
            {"since": since},
        ).mappings().first()

        attempted = int(row["matches_attempted"] or 0)
        with_odds = int(row["matches_with_odds"] or 0)
        unavailable = int(row["matches_marked_unavailable"] or 0)

        return {
            "matches_attempted": attempted,
            "matches_with_odds": with_odds,
            "matches_marked_unavailable": unavailable,
            "finished_attempts": int(row["finished_attempts"] or 0),
            "upcoming_attempts": int(row["upcoming_attempts"] or 0),
            "exhausted_without_odds": int(row["exhausted_without_odds"] or 0),
            "success_rate": round(with_odds / attempted, 4) if attempted else 0.0,
            "empty_or_unavailable_rate": round(unavailable / attempted, 4) if attempted else 0.0,
        }

    def stats_ingestion_since(self, since: datetime) -> dict[str, Any]:
        row = self.session.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE stats_attempted_at >= :since
                    ) AS matches_attempted,

                    COUNT(*) FILTER (
                        WHERE stats_attempted_at >= :since
                        AND has_stats = TRUE
                    ) AS matches_with_stats,

                    COUNT(*) FILTER (
                        WHERE stats_attempted_at >= :since
                        AND stats_unavailable = TRUE
                    ) AS matches_marked_unavailable,

                    COUNT(*) FILTER (
                        WHERE stats_attempted_at >= :since
                        AND stats_attempt_count >= 1
                        AND has_stats = FALSE
                    ) AS exhausted_without_stats
                FROM matches
                """
            ),
            {"since": since},
        ).mappings().first()

        attempted = int(row["matches_attempted"] or 0)
        with_stats = int(row["matches_with_stats"] or 0)
        unavailable = int(row["matches_marked_unavailable"] or 0)

        return {
            "matches_attempted": attempted,
            "matches_with_stats": with_stats,
            "matches_marked_unavailable": unavailable,
            "exhausted_without_stats": int(row["exhausted_without_stats"] or 0),
            "success_rate": round(with_stats / attempted, 4) if attempted else 0.0,
            "empty_or_unavailable_rate": round(unavailable / attempted, 4) if attempted else 0.0,
        }

    def league_waste_since(self, since: datetime, limit: int = 30) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text(
                """
                SELECT
                    league,

                    COUNT(*) FILTER (
                        WHERE odds_attempted_at >= :since
                    ) AS odds_attempts,

                    COUNT(*) FILTER (
                        WHERE odds_attempted_at >= :since
                        AND has_odds = TRUE
                    ) AS odds_successes,

                    COUNT(*) FILTER (
                        WHERE odds_attempted_at >= :since
                        AND odds_unavailable = TRUE
                    ) AS odds_empty,

                    COUNT(*) FILTER (
                        WHERE stats_attempted_at >= :since
                    ) AS stats_attempts,

                    COUNT(*) FILTER (
                        WHERE stats_attempted_at >= :since
                        AND has_stats = TRUE
                    ) AS stats_successes,

                    COUNT(*) FILTER (
                        WHERE stats_attempted_at >= :since
                        AND stats_unavailable = TRUE
                    ) AS stats_empty
                FROM matches
                WHERE odds_attempted_at >= :since
                   OR stats_attempted_at >= :since
                GROUP BY league
                ORDER BY
                    (
                        COUNT(*) FILTER (
                            WHERE odds_attempted_at >= :since
                            AND odds_unavailable = TRUE
                        )
                        +
                        COUNT(*) FILTER (
                            WHERE stats_attempted_at >= :since
                            AND stats_unavailable = TRUE
                        )
                    ) DESC,
                    league ASC
                LIMIT :limit
                """
            ),
            {"since": since, "limit": limit},
        ).mappings().all()

        output = []

        for row in rows:
            odds_attempts = int(row["odds_attempts"] or 0)
            odds_empty = int(row["odds_empty"] or 0)
            stats_attempts = int(row["stats_attempts"] or 0)
            stats_empty = int(row["stats_empty"] or 0)

            output.append(
                {
                    "league": row["league"],
                    "odds_attempts": odds_attempts,
                    "odds_successes": int(row["odds_successes"] or 0),
                    "odds_empty": odds_empty,
                    "odds_waste_rate": round(odds_empty / odds_attempts, 4) if odds_attempts else 0.0,
                    "stats_attempts": stats_attempts,
                    "stats_successes": int(row["stats_successes"] or 0),
                    "stats_empty": stats_empty,
                    "stats_waste_rate": round(stats_empty / stats_attempts, 4) if stats_attempts else 0.0,
                }
            )

        return output

    def finished_match_waste_since(self, since: datetime) -> dict[str, Any]:
        row = self.session.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE is_finished = TRUE
                        AND odds_attempted_at >= :since
                    ) AS finished_odds_attempts,

                    COUNT(*) FILTER (
                        WHERE is_finished = TRUE
                        AND odds_attempted_at >= :since
                        AND has_odds = TRUE
                    ) AS finished_odds_successes,

                    COUNT(*) FILTER (
                        WHERE is_finished = TRUE
                        AND odds_attempted_at >= :since
                        AND odds_unavailable = TRUE
                    ) AS finished_odds_empty,

                    COUNT(*) FILTER (
                        WHERE is_finished = TRUE
                        AND stats_attempted_at >= :since
                    ) AS finished_stats_attempts,

                    COUNT(*) FILTER (
                        WHERE is_finished = TRUE
                        AND stats_attempted_at >= :since
                        AND has_stats = TRUE
                    ) AS finished_stats_successes,

                    COUNT(*) FILTER (
                        WHERE is_finished = TRUE
                        AND stats_attempted_at >= :since
                        AND stats_unavailable = TRUE
                    ) AS finished_stats_empty
                FROM matches
                """
            ),
            {"since": since},
        ).mappings().first()

        odds_attempts = int(row["finished_odds_attempts"] or 0)
        odds_empty = int(row["finished_odds_empty"] or 0)

        stats_attempts = int(row["finished_stats_attempts"] or 0)
        stats_empty = int(row["finished_stats_empty"] or 0)

        return {
            "finished_odds_attempts": odds_attempts,
            "finished_odds_successes": int(row["finished_odds_successes"] or 0),
            "finished_odds_empty": odds_empty,
            "finished_odds_waste_rate": round(odds_empty / odds_attempts, 4) if odds_attempts else 0.0,
            "finished_stats_attempts": stats_attempts,
            "finished_stats_successes": int(row["finished_stats_successes"] or 0),
            "finished_stats_empty": stats_empty,
            "finished_stats_waste_rate": round(stats_empty / stats_attempts, 4) if stats_attempts else 0.0,
        }

    def upcoming_match_waste_since(self, since: datetime) -> dict[str, Any]:
        row = self.session.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE is_finished = FALSE
                        AND odds_attempted_at >= :since
                    ) AS upcoming_odds_attempts,

                    COUNT(*) FILTER (
                        WHERE is_finished = FALSE
                        AND odds_attempted_at >= :since
                        AND has_odds = TRUE
                    ) AS upcoming_odds_successes,

                    COUNT(*) FILTER (
                        WHERE is_finished = FALSE
                        AND odds_attempted_at >= :since
                        AND odds_unavailable = TRUE
                    ) AS upcoming_odds_empty
                FROM matches
                """
            ),
            {"since": since},
        ).mappings().first()

        attempts = int(row["upcoming_odds_attempts"] or 0)
        empty = int(row["upcoming_odds_empty"] or 0)

        return {
            "upcoming_odds_attempts": attempts,
            "upcoming_odds_successes": int(row["upcoming_odds_successes"] or 0),
            "upcoming_odds_empty": empty,
            "upcoming_odds_waste_rate": round(empty / attempts, 4) if attempts else 0.0,
        }

    def api_waste_report(self, days: int = 1) -> dict[str, Any]:
        since = datetime.utcnow() - timedelta(days=days)

        odds = self.odds_ingestion_since(since)
        stats = self.stats_ingestion_since(since)
        finished = self.finished_match_waste_since(since)
        upcoming = self.upcoming_match_waste_since(since)

        total_attempts = (
            odds["matches_attempted"]
            + stats["matches_attempted"]
        )

        total_empty = (
            odds["matches_marked_unavailable"]
            + stats["matches_marked_unavailable"]
        )

        return {
            "window_days": days,
            "generated_at": datetime.utcnow().isoformat(),
            "total_ingestion_attempts": total_attempts,
            "total_empty_or_unavailable": total_empty,
            "overall_waste_rate": round(total_empty / total_attempts, 4) if total_attempts else 0.0,
            "odds": odds,
            "stats": stats,
            "finished_matches": finished,
            "upcoming_matches": upcoming,
        }