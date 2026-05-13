# backend/app/services/ecosystem_odds_orchestrator.py

from collections import defaultdict

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from app.db.models import Match
from app.ingest.football_odds_ingestion import ingest_odds_for_fixture
from app.services.league_cooldown_service import LeagueCooldownService


PRIORITY_WEIGHTS = {
    "CORE_PRODUCTION": 1.00,
    "HIGH_PRIORITY": 0.85,
    "GROWTH_PRIORITY": 0.65,
    "EXPLORATION_PRIORITY": 0.45,
    "DISCOVERY_ROTATION": 0.25,
}


MAX_MATCHES_PER_LEAGUE = 3


class EcosystemOddsOrchestrator:
    """
    Self-learning ecosystem-driven odds orchestration.

    - No permanent whitelist
    - No permanent exclusion
    - DB-driven league maturity
    - Cooldown protection
    - League diversity
    - Priority-weighted routing
    - Adaptive waste reduction
    """

    def __init__(
        self,
        session: Session,
        limit: int = 500,
        force: bool = False,
        use_league_cooldown: bool = True,
    ):
        self.session = session
        self.limit = limit
        self.force = force
        self.use_league_cooldown = use_league_cooldown
        self.cooldown_service = LeagueCooldownService(session=session)

    def run(self) -> dict:
        matches = self._select_candidate_matches()

        processed = 0
        failed = 0
        failures = []
        sample_results = []

        skipped_by_cooldown = 0

        for match in matches:
            try:
                priority_tier = self._resolve_priority_tier(match.league)
                cooldown_status = self.cooldown_service.get_league_cooldown_status(
                    match.league
                )

                if (
                    self.use_league_cooldown
                    and cooldown_status["cooldown_active"]
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
                            "provider_fixture_id": match.provider_fixture_id,
                            "league": match.league,
                            "priority_tier": priority_tier,
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
                            "provider_fixture_id": match.provider_fixture_id,
                            "league": match.league,
                            "home_team": match.home_team,
                            "away_team": match.away_team,
                            "error": str(exc),
                        }
                    )

        return {
            "matches_selected": len(matches),
            "matches_processed": processed,
            "matches_skipped_by_cooldown": skipped_by_cooldown,
            "matches_failed": failed,
            "failures": failures,
            "sample_results": sample_results,
        }

    def _select_candidate_matches(self) -> list[Match]:
        cooldown_filter = or_(
            Match.odds_unavailable == False,
            and_(
                Match.odds_unavailable == True,
                Match.odds_attempt_count < 3,
                Match.odds_attempted_at
                < func.now() - text("INTERVAL '24 hours'"),
            ),
        )

        candidates = list(
            self.session.scalars(
                select(Match)
                .where(Match.is_finished == False)
                .where(Match.is_cancelled == False)
                .where(Match.is_postponed == False)
                .where(Match.has_odds == False)
                .where(Match.provider_fixture_id.is_not(None))
                .where(Match.kickoff_datetime >= func.now())
                .where(cooldown_filter)
                .order_by(Match.kickoff_datetime.asc())
                .limit(self.limit * 10)
            )
        )

        scored = []

        for match in candidates:
            priority_tier = self._resolve_priority_tier(match.league)
            priority_weight = PRIORITY_WEIGHTS.get(
                priority_tier,
                PRIORITY_WEIGHTS["DISCOVERY_ROTATION"],
            )

            attempt_penalty = min(float(match.odds_attempt_count or 0) * 0.08, 0.25)

            league_adjustment = 0.0

            if self.use_league_cooldown and not self.force:
                cooldown_status = self.cooldown_service.get_league_cooldown_status(
                    match.league
                )

                if cooldown_status["cooldown_active"]:
                    continue

                league_adjustment = self.cooldown_service.league_score_adjustment(
                    match.league
                )

            score = priority_weight - attempt_penalty + league_adjustment

            scored.append(
                {
                    "score": score,
                    "priority_tier": priority_tier,
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

            if league_counts[league_key] >= MAX_MATCHES_PER_LEAGUE:
                continue

            selected.append(match)
            league_counts[league_key] += 1

            if len(selected) >= self.limit:
                break

        return selected

    def _resolve_priority_tier(self, league: str | None) -> str:
        if not league:
            return "DISCOVERY_ROTATION"

        row = self.session.execute(
            text(
                """
                SELECT priority_tier
                FROM league_odds_coverage_snapshots
                WHERE league = :league
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ),
            {"league": league},
        ).mappings().first()

        if not row:
            return "DISCOVERY_ROTATION"

        return row.get("priority_tier") or "DISCOVERY_ROTATION"