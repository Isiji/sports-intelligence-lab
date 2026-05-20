# backend/app/services/league_cooldown_service.py

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class LeagueCooldownService:
    """
    Adaptive league cooldown intelligence.

    Important:
    - Odds cooldowns are SHORT because provider odds can disappear quickly.
    - Stats cooldowns can be longer because stats remain available longer.
    - No permanent whitelist.
    - No permanent exclusion.
    """

    def __init__(
        self,
        session: Session,
        lookback_days: int = 2,
        min_attempts: int = 5,
    ):
        self.session = session
        self.lookback_days = lookback_days
        self.min_attempts = min_attempts

    def get_league_cooldown_status(
        self,
        league: str | None,
        data_type: str = "odds",
    ) -> dict[str, Any]:
        if not league:
            return self._allowed(
                league=league,
                reason="no league supplied",
            )

        data_type = (data_type or "odds").lower().strip()

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

        if data_type == "stats":
            attempts = int(row["stats_attempts"] or 0)
            successes = int(row["stats_successes"] or 0)
            empty = int(row["stats_empty"] or 0)
            last_attempted_at = row["last_stats_attempted_at"]
        else:
            attempts = int(row["odds_attempts"] or 0)
            successes = int(row["odds_successes"] or 0)
            empty = int(row["odds_empty"] or 0)
            last_attempted_at = row["last_odds_attempted_at"]

        if attempts < self.min_attempts:
            return {
                "league": league,
                "data_type": data_type,
                "cooldown_active": False,
                "cooldown_hours": 0,
                "cooldown_until": None,
                "reason": "not enough attempts for cooldown decision",
                "score": 0.0,
                "attempts": attempts,
                "successes": successes,
                "empty": empty,
                "waste_rate": 0.0,
                "success_rate": 0.0,
            }

        waste_rate = empty / attempts if attempts else 0.0
        success_rate = successes / attempts if attempts else 0.0

        cooldown_minutes = self._resolve_cooldown_minutes(
            data_type=data_type,
            waste_rate=waste_rate,
            success_rate=success_rate,
            attempts=attempts,
        )

        cooldown_active = False
        cooldown_until = None

        if cooldown_minutes > 0 and last_attempted_at is not None:
            cooldown_until = last_attempted_at + timedelta(minutes=cooldown_minutes)
            cooldown_active = datetime.utcnow() < cooldown_until

        return {
            "league": league,
            "data_type": data_type,
            "cooldown_active": cooldown_active,
            "cooldown_minutes": cooldown_minutes,
            "cooldown_hours": round(cooldown_minutes / 60, 2),
            "cooldown_until": cooldown_until.isoformat() if cooldown_until else None,
            "reason": self._reason(
                data_type=data_type,
                waste_rate=waste_rate,
                success_rate=success_rate,
                cooldown_minutes=cooldown_minutes,
            ),
            "score": round(success_rate - waste_rate, 4),
            "attempts": attempts,
            "successes": successes,
            "empty": empty,
            "waste_rate": round(waste_rate, 4),
            "success_rate": round(success_rate, 4),
        }

    def build_cooldown_report(
        self,
        limit: int = 50,
        data_type: str = "odds",
    ) -> dict[str, Any]:
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
            self.get_league_cooldown_status(
                row["league"],
                data_type=data_type,
            )
            for row in rows
        ]

        leagues.sort(
            key=lambda item: (
                item.get("cooldown_active", False),
                item.get("waste_rate", 0.0),
                item.get("attempts", 0),
            ),
            reverse=True,
        )

        return {
            "lookback_days": self.lookback_days,
            "min_attempts": self.min_attempts,
            "data_type": data_type,
            "generated_at": datetime.utcnow().isoformat(),
            "leagues": leagues,
        }

    def should_skip_league(
        self,
        league: str | None,
        data_type: str = "odds",
    ) -> bool:
        status = self.get_league_cooldown_status(
            league,
            data_type=data_type,
        )
        return bool(status["cooldown_active"])

    def league_score_adjustment(
        self,
        league: str | None,
        data_type: str = "odds",
    ) -> float:
        status = self.get_league_cooldown_status(
            league,
            data_type=data_type,
        )

        if status["cooldown_active"]:
            return -0.55 if data_type == "odds" else -1.0

        success_rate = float(status.get("success_rate", 0.0) or 0.0)
        waste_rate = float(status.get("waste_rate", 0.0) or 0.0)

        if success_rate >= 0.50:
            return 0.20

        if success_rate >= 0.35:
            return 0.10

        if waste_rate >= 0.90:
            return -0.20 if data_type == "odds" else -0.35

        if waste_rate >= 0.80:
            return -0.12 if data_type == "odds" else -0.25

        if waste_rate >= 0.65:
            return -0.05 if data_type == "odds" else -0.12

        return 0.0

    def _resolve_cooldown_minutes(
        self,
        data_type: str,
        waste_rate: float,
        success_rate: float,
        attempts: int,
    ) -> int:
        if attempts < self.min_attempts:
            return 0

        if success_rate >= 0.50:
            return 0

        if data_type == "odds":
            if waste_rate >= 0.95:
                return 180

            if waste_rate >= 0.90:
                return 120

            if waste_rate >= 0.80:
                return 90

            if waste_rate >= 0.65:
                return 45

            return 0

        if waste_rate >= 0.95:
            return 1440

        if waste_rate >= 0.90:
            return 720

        if waste_rate >= 0.80:
            return 360

        if waste_rate >= 0.65:
            return 180

        return 0

    def _reason(
        self,
        data_type: str,
        waste_rate: float,
        success_rate: float,
        cooldown_minutes: int,
    ) -> str:
        if cooldown_minutes <= 0:
            return "league allowed"

        return (
            f"temporary {data_type} cooldown: "
            f"waste_rate={round(waste_rate, 4)}, "
            f"success_rate={round(success_rate, 4)}, "
            f"cooldown_minutes={cooldown_minutes}"
        )

    def _allowed(
        self,
        league: str | None,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "league": league,
            "data_type": "odds",
            "cooldown_active": False,
            "cooldown_minutes": 0,
            "cooldown_hours": 0,
            "cooldown_until": None,
            "reason": reason,
            "score": 0.0,
        }