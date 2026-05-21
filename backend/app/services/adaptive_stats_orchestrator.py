from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Match
from app.ingest.football_stats_ingestion import (
    ingest_fixture_statistics,
)
from app.services.adaptive_ingestion_decision_engine import (
    AdaptiveIngestionDecisionEngine,
    CHANNEL_STATS,
)


MAX_MATCHES_PER_LEAGUE = 5


class AdaptiveStatsOrchestrator:
    """
    Autonomous adaptive stats ingestion.

    Goals:
    - minimize wasted API calls
    - maximize real stats enrichment
    - prioritize productive ecosystems
    - respect adaptive cooldown intelligence
    - preserve API budget
    """

    def __init__(
        self,
        session: Session,
        limit: int = 300,
        season: int | None = None,
        leagues: list[str] | None = None,
        force: bool = False,
    ):
        self.session = session
        self.limit = int(limit)
        self.season = season
        self.leagues = [
            x.strip()
            for x in (leagues or [])
            if x.strip()
        ]
        self.force = force

        self.engine = AdaptiveIngestionDecisionEngine(
            session=session
        )

    # =====================================================
    # MAIN
    # =====================================================

    def run(self) -> dict[str, Any]:

        matches = self._select_candidate_matches()

        processed = 0
        skipped = 0
        unavailable = 0
        failed = 0

        skipped_by_engine = 0

        failures = []
        sample_results = []

        for match in matches:

            decision = self.engine.decide(
                match=match,
                channel=CHANNEL_STATS,
                force=self.force,
            )

            if not decision.eligible:
                skipped_by_engine += 1
                continue

            try:
                result = ingest_fixture_statistics(
                    session=self.session,
                    match_id=match.id,
                    force=self.force,
                )

                if result.get("skipped"):
                    skipped += 1

                elif result.get("has_stats"):
                    processed += 1

                elif result.get("stats_unavailable"):
                    unavailable += 1

                if len(sample_results) < 20:
                    sample_results.append(
                        {
                            "match_id": match.id,
                            "league": match.league,
                            "season": match.season,
                            "score": decision.score,
                            "priority_tier": decision.priority_tier,
                            "waste_rate": decision.waste_rate,
                            "success_rate": decision.success_rate,
                            "recommended_budget_weight": (
                                decision.recommended_budget_weight
                            ),
                            "home_team": match.home_team,
                            "away_team": match.away_team,
                            "result": result,
                        }
                    )

            except Exception as exc:

                failed += 1

                self.session.rollback()

                if len(failures) < 20:
                    failures.append(
                        {
                            "match_id": match.id,
                            "league": match.league,
                            "error": str(exc),
                        }
                    )

                if (
                    "Daily API safety limit reached"
                    in str(exc)
                ):
                    break

        return {
            "season": self.season,
            "leagues": self.leagues,
            "matches_selected": len(matches),
            "matches_processed": processed,
            "matches_skipped": skipped,
            "matches_skipped_by_engine": skipped_by_engine,
            "matches_unavailable": unavailable,
            "matches_failed": failed,
            "failures": failures,
            "sample_results": sample_results,
        }

    # =====================================================
    # CANDIDATES
    # =====================================================

    def _select_candidate_matches(
        self,
    ) -> list[Match]:

        conditions = [
            Match.provider == "api-football",

            Match.provider_fixture_id.isnot(None),

            Match.is_finished.is_(True),

            Match.is_cancelled.is_(False),

            Match.is_postponed.is_(False),

            Match.home_goals.isnot(None),

            Match.away_goals.isnot(None),

            Match.has_stats.is_(False),
        ]

        if self.season is not None:
            conditions.append(
                Match.season == self.season
            )

        if self.leagues:
            conditions.append(
                Match.league.in_(self.leagues)
            )

        candidates = list(
            self.session.scalars(
                select(Match)
                .where(*conditions)
                .order_by(
                    Match.kickoff_datetime.desc().nulls_last(),
                    Match.id.desc(),
                )
                .limit(self.limit * 10)
            )
        )

        scored = []

        for match in candidates:

            decision = self.engine.decide(
                match=match,
                channel=CHANNEL_STATS,
                force=self.force,
            )

            if not decision.eligible:
                continue

            scored.append(
                {
                    "score": decision.score,
                    "match": match,
                    "decision": decision,
                }
            )

        scored.sort(
            key=lambda item: (
                item["score"],
                item["match"].kickoff_datetime
                or func.now(),
            ),
            reverse=True,
        )

        selected = []

        per_league: dict[str, int] = defaultdict(int)

        for item in scored:

            match = item["match"]

            league = match.league or "UNKNOWN"

            if (
                per_league[league]
                >= MAX_MATCHES_PER_LEAGUE
            ):
                continue

            selected.append(match)

            per_league[league] += 1

            if len(selected) >= self.limit:
                break

        return selected