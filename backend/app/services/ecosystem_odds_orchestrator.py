# backend/app/services/ecosystem_odds_orchestrator.py

from collections import defaultdict

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from app.db.models import Match
from app.ingest.football_odds_ingestion import ingest_odds_for_fixture
from app.services.league_cooldown_service import LeagueCooldownService


PRIORITY_WEIGHTS = {
    "CORE_PRODUCTION": 1.25,
    "HIGH_PRIORITY": 1.05,
    "GROWTH_PRIORITY": 0.82,
    "EXPLORATION_PRIORITY": 0.42,
    "DISCOVERY_ROTATION": 0.08,
}


MAX_MATCHES_PER_LEAGUE = 5


class EcosystemOddsOrchestrator:
    """
    Self-learning ecosystem-driven odds orchestration.

    Production-safe:
    - no permanent whitelist
    - no permanent exclusion
    - DB-driven league maturity
    - cooldown protection
    - league diversity
    - priority-weighted routing
    - adaptive waste reduction
    """

    def __init__(
        self,
        session: Session,
        limit: int = 500,
        force: bool = False,
        use_league_cooldown: bool = True,
    ):
        self.session = session
        self.limit = int(limit)
        self.force = force
        self.use_league_cooldown = use_league_cooldown
        self.cooldown_service = LeagueCooldownService(
            session=session
        )

    def run(self) -> dict:
        matches = self._select_candidate_matches()

        processed = 0
        failed = 0
        failures = []
        sample_results = []

        skipped_by_cooldown = 0

        for match in matches:
            try:
                snapshot = self._resolve_league_snapshot(
                    match.league
                )

                cooldown_status = (
                    self.cooldown_service
                    .get_league_cooldown_status(
                        match.league
                    )
                )

                if (
                    self.use_league_cooldown
                    and cooldown_status[
                        "cooldown_active"
                    ]
                    and not self.force
                ):
                    skipped_by_cooldown += 1
                    continue

                result = ingest_odds_for_fixture(
                    self.session,
                    match.id,
                    force=self.force,
                )

                processed += 1

                if len(sample_results) < 20:
                    sample_results.append(
                        {
                            "match_id": match.id,
                            "provider_fixture_id": (
                                match.provider_fixture_id
                            ),
                            "league": match.league,
                            "priority_tier": (
                                snapshot["priority_tier"]
                            ),
                            "ecosystem_score": (
                                snapshot["ecosystem_score"]
                            ),
                            "coverage_score": (
                                snapshot["coverage_score"]
                            ),
                            "bookmaker_count": (
                                snapshot["bookmaker_count"]
                            ),
                            "supported_market_count": (
                                snapshot[
                                    "supported_market_count"
                                ]
                            ),
                            "cooldown": cooldown_status,
                            "home_team": match.home_team,
                            "away_team": match.away_team,
                            "result": result,
                        }
                    )

            except Exception as exc:
                failed += 1

                if len(failures) < 20:
                    failures.append(
                        {
                            "match_id": match.id,
                            "provider_fixture_id": (
                                match.provider_fixture_id
                            ),
                            "league": match.league,
                            "home_team": match.home_team,
                            "away_team": match.away_team,
                            "error": str(exc),
                        }
                    )

        return {
            "matches_selected": len(matches),
            "matches_processed": processed,
            "matches_skipped_by_cooldown": (
                skipped_by_cooldown
            ),
            "matches_failed": failed,
            "failures": failures,
            "sample_results": sample_results,
        }

    def _select_candidate_matches(
        self,
    ) -> list[Match]:

        cooldown_filter = or_(
            Match.odds_unavailable == False,
            and_(
                Match.odds_unavailable == True,
                Match.odds_attempt_count < 3,
                Match.odds_attempted_at
                < func.now()
                - text("INTERVAL '48 hours'"),
            ),
        )

        candidates = list(
            self.session.scalars(
                select(Match)
                .where(Match.is_finished == False)
                .where(Match.is_cancelled == False)
                .where(Match.is_postponed == False)
                .where(Match.has_odds == False)
                .where(
                    Match.provider_fixture_id.is_not(None)
                )
                .where(
                    Match.kickoff_datetime >= func.now()
                )
                .where(cooldown_filter)
                .order_by(
                    Match.kickoff_datetime.asc()
                )
                .limit(self.limit * 15)
            )
        )

        scored = []

        for match in candidates:
            snapshot = self._resolve_league_snapshot(
                match.league
            )

            priority_weight = PRIORITY_WEIGHTS.get(
                snapshot["priority_tier"],
                PRIORITY_WEIGHTS[
                    "DISCOVERY_ROTATION"
                ],
            )

            attempt_penalty = min(
                float(
                    match.odds_attempt_count or 0
                )
                * 0.10,
                0.35,
            )

            maturity_bonus = min(
                float(
                    snapshot["ecosystem_score"]
                    or 0.0
                )
                / 100.0,
                1.0,
            ) * 0.30

            bookmaker_bonus = min(
                float(
                    snapshot["bookmaker_count"]
                    or 0
                )
                / 12.0,
                1.0,
            ) * 0.12

            market_bonus = min(
                float(
                    snapshot[
                        "supported_market_count"
                    ]
                    or 0
                )
                / 250.0,
                1.0,
            ) * 0.10

            league_adjustment = 0.0

            if self.use_league_cooldown and not self.force:
                cooldown_status = (
                    self.cooldown_service
                    .get_league_cooldown_status(
                        match.league
                    )
                )

                if cooldown_status[
                    "cooldown_active"
                ]:
                    continue

                league_adjustment = (
                    self.cooldown_service
                    .league_score_adjustment(
                        match.league
                    )
                )

            score = (
                priority_weight
                + maturity_bonus
                + bookmaker_bonus
                + market_bonus
                + league_adjustment
                - attempt_penalty
            )

            scored.append(
                {
                    "score": score,
                    "priority_tier": (
                        snapshot["priority_tier"]
                    ),
                    "match": match,
                }
            )

        scored.sort(
            key=lambda item: (
                item["score"],
                item["match"].kickoff_datetime,
            ),
            reverse=True,
        )

        selected = []
        league_counts = defaultdict(int)

        for item in scored:
            match = item["match"]
            league_key = match.league or "UNKNOWN"

            tier = item["priority_tier"]

            league_limit = self._league_limit_for_tier(
                tier
            )

            if league_counts[league_key] >= league_limit:
                continue

            selected.append(match)
            league_counts[league_key] += 1

            if len(selected) >= self.limit:
                break

        return selected

    def _league_limit_for_tier(
        self,
        priority_tier: str,
    ) -> int:

        if priority_tier == "CORE_PRODUCTION":
            return 8

        if priority_tier == "HIGH_PRIORITY":
            return 7

        if priority_tier == "GROWTH_PRIORITY":
            return 5

        if priority_tier == "EXPLORATION_PRIORITY":
            return 3

        return 1

    def _resolve_league_snapshot(
        self,
        league: str | None,
    ) -> dict:

        if not league:
            return {
                "priority_tier": "DISCOVERY_ROTATION",
                "ecosystem_score": 0.0,
                "coverage_score": 0.0,
                "bookmaker_count": 0,
                "supported_market_count": 0,
            }

        row = self.session.execute(
            text(
                """
                SELECT
                    priority_tier,
                    ecosystem_score,
                    coverage_score,
                    bookmaker_count,
                    supported_market_count
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
                "priority_tier": "DISCOVERY_ROTATION",
                "ecosystem_score": 0.0,
                "coverage_score": 0.0,
                "bookmaker_count": 0,
                "supported_market_count": 0,
            }

        return {
            "priority_tier": (
                row["priority_tier"]
                or "DISCOVERY_ROTATION"
            ),
            "ecosystem_score": float(
                row["ecosystem_score"] or 0.0
            ),
            "coverage_score": float(
                row["coverage_score"] or 0.0
            ),
            "bookmaker_count": int(
                row["bookmaker_count"] or 0
            ),
            "supported_market_count": int(
                row["supported_market_count"] or 0
            ),
        }

    def _resolve_priority_tier(
        self,
        league: str | None,
    ) -> str:
        return self._resolve_league_snapshot(
            league
        )["priority_tier"]