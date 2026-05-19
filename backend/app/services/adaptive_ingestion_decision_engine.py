# backend/app/services/adaptive_ingestion_decision_engine.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Match
from app.services.league_cooldown_service import LeagueCooldownService


CHANNEL_ODDS = "odds"
CHANNEL_STATS = "stats"
CHANNEL_FINISHED = "finished"
CHANNEL_FIXTURES = "fixtures"


@dataclass
class IngestionDecision:
    eligible: bool
    score: float
    reason: str

    retry_after_hours: int

    cooldown_active: bool

    priority_tier: str

    waste_rate: float
    success_rate: float

    recommended_budget_weight: float

    metadata: dict[str, Any]


class AdaptiveIngestionDecisionEngine:
    """
    Universal autonomous ingestion intelligence.

    Shared adaptive brain for:
    - odds ingestion
    - stats ingestion
    - fixture refresh
    - finished updates
    - bookmaker ecosystem enrichment

    Philosophy:
    - preserve exploration
    - reduce waste gradually
    - avoid hard ecosystem death
    - reward productive leagues
    - learn long-term ecosystem quality
    """

    def __init__(
        self,
        session: Session,
    ):
        self.session = session
        self.cooldown_service = LeagueCooldownService(
            session=session
        )

    # =====================================================
    # MAIN
    # =====================================================

    def decide(
        self,
        match: Match,
        channel: str,
        force: bool = False,
    ) -> IngestionDecision:

        if force:
            return IngestionDecision(
                eligible=True,
                score=999.0,
                reason="forced",
                retry_after_hours=0,
                cooldown_active=False,
                priority_tier="FORCED",
                waste_rate=0.0,
                success_rate=1.0,
                recommended_budget_weight=1.0,
                metadata={},
            )

        base_validation = self._base_validation(
            match=match,
            channel=channel,
        )

        if not base_validation["eligible"]:
            return IngestionDecision(
                eligible=False,
                score=-999.0,
                reason=base_validation["reason"],
                retry_after_hours=0,
                cooldown_active=False,
                priority_tier="BLOCKED",
                waste_rate=0.0,
                success_rate=0.0,
                recommended_budget_weight=0.0,
                metadata={},
            )

        cooldown = (
            self.cooldown_service
            .get_league_cooldown_status(
                match.league
            )
        )

        if cooldown["cooldown_active"]:

            return IngestionDecision(
                eligible=False,
                score=-100.0,
                reason="league_cooldown_active",
                retry_after_hours=int(
                    cooldown.get(
                        "cooldown_hours",
                        24,
                    )
                ),
                cooldown_active=True,
                priority_tier="COOLDOWN",
                waste_rate=float(
                    cooldown.get(
                        "waste_rate",
                        0.0,
                    )
                ),
                success_rate=float(
                    cooldown.get(
                        "success_rate",
                        0.0,
                    )
                ),
                recommended_budget_weight=0.0,
                metadata={
                    "cooldown": cooldown,
                },
            )

        ecosystem = self._ecosystem_snapshot(
            match.league
        )

        telemetry = self._league_telemetry(
            league=match.league,
            channel=channel,
        )

        kickoff_bonus = self._kickoff_bonus(
            match=match,
            channel=channel,
        )

        retry_penalty = self._retry_penalty(
            match=match,
            channel=channel,
        )

        # =====================================================
        # ADAPTIVE ECOSYSTEM SCORING
        # =====================================================

        ecosystem_bonus = (
            ecosystem["ecosystem_score"] / 100.0
        ) * 0.55

        success_bonus = (
            telemetry["success_rate"] * 0.40
        )

        waste_penalty = (
            telemetry["waste_rate"] * 0.65
        )

        score = (
            ecosystem_bonus
            + success_bonus
            + kickoff_bonus
            - waste_penalty
            - retry_penalty
        )

        # =====================================================
        # SOFT DECAY
        #
        # Avoid hard ecosystem death.
        # Deprioritize instead.
        # =====================================================

        if (
            telemetry["waste_rate"] >= 0.90
            and telemetry["success_rate"] <= 0.05
        ):
            score -= 0.35

        elif (
            telemetry["waste_rate"] >= 0.75
            and telemetry["success_rate"] <= 0.10
        ):
            score -= 0.20

        elif (
            telemetry["waste_rate"] >= 0.60
            and telemetry["success_rate"] <= 0.20
        ):
            score -= 0.10

        # =====================================================
        # EXPLORATION PRESERVATION
        #
        # Keep discovery alive.
        # =====================================================

        if ecosystem["priority_tier"] in {
            "DISCOVERY_ROTATION",
            "EXPLORATION_PRIORITY",
        }:
            score += 0.05

        # =====================================================
        # HEALTHY ECOSYSTEM BOOST
        # =====================================================

        if telemetry["success_rate"] >= 0.60:
            score += 0.10

        if telemetry["success_rate"] >= 0.75:
            score += 0.15

        if telemetry["waste_rate"] <= 0.20:
            score += 0.10

        # =====================================================
        # EXECUTABLE ECOSYSTEM BONUS
        # =====================================================

        if (
            ecosystem.get(
                "supported_market_count",
                0,
            ) >= 25
        ):
            score += 0.08

        if (
            ecosystem.get(
                "bookmaker_count",
                0,
            ) >= 8
        ):
            score += 0.08

        # =====================================================
        # FINAL ELIGIBILITY
        # =====================================================

        eligible = score >= -0.05

        retry_after_hours = (
            self._resolve_retry_hours(
                waste_rate=telemetry["waste_rate"],
                success_rate=telemetry["success_rate"],
                attempt_count=self._attempt_count(
                    match=match,
                    channel=channel,
                ),
            )
        )

        return IngestionDecision(
            eligible=eligible,
            score=round(score, 4),
            reason=(
                "eligible"
                if eligible
                else "score_below_threshold"
            ),
            retry_after_hours=retry_after_hours,
            cooldown_active=False,
            priority_tier=ecosystem["priority_tier"],
            waste_rate=telemetry["waste_rate"],
            success_rate=telemetry["success_rate"],
            recommended_budget_weight=max(
                min(score + 0.5, 1.0),
                0.0,
            ),
            metadata={
                "ecosystem": ecosystem,
                "telemetry": telemetry,
                "kickoff_bonus": kickoff_bonus,
                "ecosystem_bonus": ecosystem_bonus,
                "success_bonus": success_bonus,
                "waste_penalty": waste_penalty,
                "retry_penalty": retry_penalty,
            },
        )

    # =====================================================
    # BASE VALIDATION
    # =====================================================

    def _base_validation(
        self,
        match: Match,
        channel: str,
    ) -> dict[str, Any]:

        if match.provider != "api-football":
            return {
                "eligible": False,
                "reason": "not_api_football",
            }

        if not match.provider_fixture_id:
            return {
                "eligible": False,
                "reason": "missing_fixture_id",
            }

        if match.is_cancelled:
            return {
                "eligible": False,
                "reason": "cancelled",
            }

        if match.is_postponed:
            return {
                "eligible": False,
                "reason": "postponed",
            }

        if channel == CHANNEL_ODDS:

            if match.has_odds:
                return {
                    "eligible": False,
                    "reason": "already_has_odds",
                }

        if channel == CHANNEL_STATS:

            if match.has_stats:
                return {
                    "eligible": False,
                    "reason": "already_has_stats",
                }

            if not match.is_finished:
                return {
                    "eligible": False,
                    "reason": "stats_require_finished_match",
                }

        return {
            "eligible": True,
            "reason": "eligible",
        }

    # =====================================================
    # ECOSYSTEM SNAPSHOT
    # =====================================================

    def _ecosystem_snapshot(
        self,
        league: str | None,
    ) -> dict[str, Any]:

        if not league:
            return {
                "priority_tier": (
                    "DISCOVERY_ROTATION"
                ),
                "ecosystem_score": 0.0,
                "coverage_score": 0.0,
                "supported_market_count": 0,
                "bookmaker_count": 0,
            }

        row = self.session.execute(
            text(
                """
                SELECT
                    priority_tier,
                    ecosystem_score,
                    coverage_score,
                    supported_market_count,
                    bookmaker_count
                FROM league_odds_coverage_snapshots
                WHERE league = :league
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ),
            {
                "league": league,
            },
        ).mappings().first()

        if not row:
            return {
                "priority_tier": (
                    "DISCOVERY_ROTATION"
                ),
                "ecosystem_score": 0.0,
                "coverage_score": 0.0,
                "supported_market_count": 0,
                "bookmaker_count": 0,
            }

        return {
            "priority_tier": (
                row["priority_tier"]
            ),
            "ecosystem_score": float(
                row["ecosystem_score"] or 0.0
            ),
            "coverage_score": float(
                row["coverage_score"] or 0.0
            ),
            "supported_market_count": int(
                row["supported_market_count"]
                or 0
            ),
            "bookmaker_count": int(
                row["bookmaker_count"] or 0
            ),
        }

    # =====================================================
    # TELEMETRY
    # =====================================================

    def _league_telemetry(
        self,
        league: str | None,
        channel: str,
    ) -> dict[str, float]:

        if not league:
            return {
                "success_rate": 0.0,
                "waste_rate": 0.0,
            }

        since = (
            datetime.utcnow()
            - timedelta(days=7)
        )

        if channel == CHANNEL_ODDS:

            row = self.session.execute(
                text(
                    """
                    SELECT
                        COUNT(*) FILTER (
                            WHERE odds_attempted_at >= :since
                        ) AS attempts,

                        COUNT(*) FILTER (
                            WHERE odds_attempted_at >= :since
                            AND has_odds = TRUE
                        ) AS successes,

                        COUNT(*) FILTER (
                            WHERE odds_attempted_at >= :since
                            AND odds_unavailable = TRUE
                        ) AS waste

                    FROM matches
                    WHERE league = :league
                    """
                ),
                {
                    "league": league,
                    "since": since,
                },
            ).mappings().first()

        else:

            row = self.session.execute(
                text(
                    """
                    SELECT
                        COUNT(*) FILTER (
                            WHERE stats_attempted_at >= :since
                        ) AS attempts,

                        COUNT(*) FILTER (
                            WHERE stats_attempted_at >= :since
                            AND has_stats = TRUE
                        ) AS successes,

                        COUNT(*) FILTER (
                            WHERE stats_attempted_at >= :since
                            AND stats_unavailable = TRUE
                        ) AS waste

                    FROM matches
                    WHERE league = :league
                    """
                ),
                {
                    "league": league,
                    "since": since,
                },
            ).mappings().first()

        attempts = int(
            row["attempts"] or 0
        )

        successes = int(
            row["successes"] or 0
        )

        waste = int(
            row["waste"] or 0
        )

        return {
            "success_rate": (
                successes / attempts
                if attempts
                else 0.0
            ),
            "waste_rate": (
                waste / attempts
                if attempts
                else 0.0
            ),
        }

    # =====================================================
    # KICKOFF BONUS
    # =====================================================

    def _kickoff_bonus(
        self,
        match: Match,
        channel: str,
    ) -> float:

        if not match.kickoff_datetime:
            return 0.0

        now = datetime.utcnow()

        delta_hours = (
            match.kickoff_datetime - now
        ).total_seconds() / 3600.0

        if channel == CHANNEL_ODDS:

            if 0 <= delta_hours <= 6:
                return 0.45

            if 6 <= delta_hours <= 24:
                return 0.30

            if 24 <= delta_hours <= 72:
                return 0.15

        if channel == CHANNEL_STATS:

            if match.is_finished:
                return 0.25

        return 0.0

    # =====================================================
    # RETRY PENALTY
    # =====================================================

    def _retry_penalty(
        self,
        match: Match,
        channel: str,
    ) -> float:

        attempts = self._attempt_count(
            match=match,
            channel=channel,
        )

        return min(
            attempts * 0.08,
            0.40,
        )

    def _attempt_count(
        self,
        match: Match,
        channel: str,
    ) -> int:

        if channel == CHANNEL_ODDS:
            return int(
                match.odds_attempt_count or 0
            )

        if channel == CHANNEL_STATS:
            return int(
                match.stats_attempt_count or 0
            )

        return 0

    # =====================================================
    # RETRY HOURS
    # =====================================================

    def _resolve_retry_hours(
        self,
        waste_rate: float,
        success_rate: float,
        attempt_count: int,
    ) -> int:

        if (
            waste_rate >= 0.90
            and success_rate <= 0.05
        ):
            return 96

        if waste_rate >= 0.80:
            return 72

        if waste_rate >= 0.65:
            return 48

        if waste_rate >= 0.50:
            return 24

        if attempt_count >= 4:
            return 72

        if attempt_count >= 3:
            return 48

        if attempt_count >= 2:
            return 24

        return 6