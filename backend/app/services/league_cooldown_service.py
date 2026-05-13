# backend/app/services/league_cooldown_service.py

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class LeagueCooldownService:
    """
    Adaptive league cooldown intelligence.

    No permanent whitelist.
    No permanent exclusion.

    Leagues with high API waste cool down temporarily.
    Leagues with good odds/stats success recover naturally.
    """

    def __init__(
        self,
        session: Session,
        lookback_days: int = 3,
        min_attempts: int = 5,
    ):
        self.session = session
        self.lookback_days = lookback_days
        self.min_attempts = min_attempts

    def get_league_cooldown_status(self, league: str | None) -> dict[str, Any]:
        if not league:
            return {
                "league": league,
                "cooldown_active": False,
                "cooldown_hours": 0,
                "reason": "no league supplied",
                "score": 0.0,
            }

        since = datetime.utcnow() - timedelta(days=self.lookback_days)

        row = self.session.execute(
            text(
                """
                SELECT
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

                    MAX(odds_attempted_at) AS last_odds_attempted_at,

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
                    ) AS stats_empty,

                    MAX(stats_attempted_at) AS last_stats_attempted_at
                FROM matches
                WHERE league = :league
                """
            ),
            {
                "league": league,
                "since": since,
            },
        ).mappings().first()

        odds_attempts = int(row["odds_attempts"] or 0)
        odds_successes = int(row["odds_successes"] or 0)
        odds_empty = int(row["odds_empty"] or 0)

        stats_attempts = int(row["stats_attempts"] or 0)
        stats_successes = int(row["stats_successes"] or 0)
        stats_empty = int(row["stats_empty"] or 0)

        total_attempts = odds_attempts + stats_attempts
        total_successes = odds_successes + stats_successes
        total_empty = odds_empty + stats_empty

        if total_attempts < self.min_attempts:
            return {
                "league": league,
                "cooldown_active": False,
                "cooldown_hours": 0,
                "reason": "not enough attempts for cooldown decision",
                "score": 0.0,
                "odds_attempts": odds_attempts,
                "odds_successes": odds_successes,
                "odds_empty": odds_empty,
                "stats_attempts": stats_attempts,
                "stats_successes": stats_successes,
                "stats_empty": stats_empty,
            }

        waste_rate = total_empty / total_attempts if total_attempts else 0.0
        success_rate = total_successes / total_attempts if total_attempts else 0.0

        cooldown_hours = self._resolve_cooldown_hours(
            waste_rate=waste_rate,
            success_rate=success_rate,
            total_attempts=total_attempts,
        )

        last_attempted_at = self._latest_datetime(
            row["last_odds_attempted_at"],
            row["last_stats_attempted_at"],
        )

        cooldown_active = False

        if cooldown_hours > 0 and last_attempted_at is not None:
            cooldown_until = last_attempted_at + timedelta(hours=cooldown_hours)
            cooldown_active = datetime.utcnow() < cooldown_until
        else:
            cooldown_until = None

        return {
            "league": league,
            "cooldown_active": cooldown_active,
            "cooldown_hours": cooldown_hours,
            "cooldown_until": cooldown_until.isoformat() if cooldown_until else None,
            "reason": self._reason(
                waste_rate=waste_rate,
                success_rate=success_rate,
                cooldown_hours=cooldown_hours,
            ),
            "score": round(success_rate - waste_rate, 4),
            "waste_rate": round(waste_rate, 4),
            "success_rate": round(success_rate, 4),
            "total_attempts": total_attempts,
            "total_successes": total_successes,
            "total_empty": total_empty,
            "odds_attempts": odds_attempts,
            "odds_successes": odds_successes,
            "odds_empty": odds_empty,
            "stats_attempts": stats_attempts,
            "stats_successes": stats_successes,
            "stats_empty": stats_empty,
        }

    def build_cooldown_report(self, limit: int = 50) -> dict[str, Any]:
        since = datetime.utcnow() - timedelta(days=self.lookback_days)

        rows = self.session.execute(
            text(
                """
                SELECT league
                FROM matches
                WHERE league IS NOT NULL
                  AND (
                        odds_attempted_at >= :since
                     OR stats_attempted_at >= :since
                  )
                GROUP BY league
                ORDER BY COUNT(*) DESC
                LIMIT :limit
                """
            ),
            {
                "since": since,
                "limit": limit,
            },
        ).mappings().all()

        leagues = [
            self.get_league_cooldown_status(row["league"])
            for row in rows
        ]

        leagues.sort(
            key=lambda item: (
                item.get("cooldown_active", False),
                item.get("waste_rate", 0.0),
                item.get("total_attempts", 0),
            ),
            reverse=True,
        )

        return {
            "lookback_days": self.lookback_days,
            "min_attempts": self.min_attempts,
            "generated_at": datetime.utcnow().isoformat(),
            "leagues": leagues,
        }

    def should_skip_league(self, league: str | None) -> bool:
        status = self.get_league_cooldown_status(league)
        return bool(status["cooldown_active"])

    def league_score_adjustment(self, league: str | None) -> float:
        status = self.get_league_cooldown_status(league)

        if status["cooldown_active"]:
            return -1.0

        success_rate = float(status.get("success_rate", 0.0) or 0.0)
        waste_rate = float(status.get("waste_rate", 0.0) or 0.0)

        if success_rate >= 0.50:
            return 0.20

        if success_rate >= 0.35:
            return 0.10

        if waste_rate >= 0.90:
            return -0.35

        if waste_rate >= 0.80:
            return -0.25

        if waste_rate >= 0.65:
            return -0.12

        return 0.0

    def _resolve_cooldown_hours(
        self,
        waste_rate: float,
        success_rate: float,
        total_attempts: int,
    ) -> int:
        if total_attempts < self.min_attempts:
            return 0

        if success_rate >= 0.50:
            return 0

        if waste_rate >= 0.95:
            return 72

        if waste_rate >= 0.90:
            return 48

        if waste_rate >= 0.80:
            return 24

        if waste_rate >= 0.65:
            return 12

        return 0

    def _reason(
        self,
        waste_rate: float,
        success_rate: float,
        cooldown_hours: int,
    ) -> str:
        if cooldown_hours <= 0:
            return "league allowed"

        return (
            f"temporary cooldown: waste_rate={round(waste_rate, 4)}, "
            f"success_rate={round(success_rate, 4)}, "
            f"cooldown_hours={cooldown_hours}"
        )

    def _latest_datetime(self, *values):
        clean_values = [value for value in values if value is not None]

        if not clean_values:
            return None

        return max(clean_values)