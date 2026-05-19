# backend/app/services/ecosystem_stats_orchestrator.py

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from app.db.models import Match
from app.ingest.football_stats_ingestion import ingest_fixture_statistics


MAX_MATCHES_PER_LEAGUE = 5

TIER_WEIGHTS = {
    "STRONG_STATS_COVERAGE": 1.00,
    "USABLE_STATS_COVERAGE": 0.80,
    "LIMITED_STATS_COVERAGE": 0.45,
    "POOR_STATS_COVERAGE": 0.15,
    "UNKNOWN": 0.25,
}


class EcosystemStatsOrchestrator:
    def __init__(
        self,
        session: Session,
        limit: int = 300,
        season: int | None = None,
        force: bool = False,
    ):
        self.session = session
        self.limit = int(limit)
        self.season = season
        self.force = force

    def run(self) -> dict[str, Any]:
        matches = self._select_candidate_matches()

        processed = 0
        skipped = 0
        unavailable = 0
        failed = 0

        failures = []
        sample_results = []

        for match in matches:
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
                            "provider_fixture_id": match.provider_fixture_id,
                            "league": match.league,
                            "season": match.season,
                            "home_team": match.home_team,
                            "away_team": match.away_team,
                            "kickoff_date": str(match.kickoff_date),
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
                            "provider_fixture_id": match.provider_fixture_id,
                            "league": match.league,
                            "season": match.season,
                            "error": str(exc),
                        }
                    )

                if "Daily API safety limit reached" in str(exc):
                    break

        return {
            "season": self.season,
            "matches_selected": len(matches),
            "matches_processed": processed,
            "matches_skipped": skipped,
            "matches_unavailable": unavailable,
            "matches_failed": failed,
            "failures": failures,
            "sample_results": sample_results,
        }

    def _select_candidate_matches(self) -> list[Match]:
        coverage = self._load_league_stats_scores()

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
            conditions.append(Match.season == self.season)

        if not self.force:
            conditions.extend(
                [
                    Match.stats_unavailable.is_(False),
                    Match.stats_attempt_count < 1,
                ]
            )

        cooldown_filter = or_(
            Match.stats_unavailable.is_(False),
            and_(
                Match.stats_unavailable.is_(True),
                Match.stats_attempt_count < 2,
                Match.stats_attempted_at < func.now() - text("INTERVAL '48 hours'"),
            ),
        )

        if not self.force:
            conditions.append(cooldown_filter)

        candidates = list(
            self.session.scalars(
                select(Match)
                .where(*conditions)
                .order_by(Match.kickoff_date.desc())
                .limit(self.limit * 10)
            )
        )

        scored = []

        for match in candidates:
            league_key = (match.league, match.season)
            row = coverage.get(league_key)

            tier = row.get("tier", "UNKNOWN") if row else "UNKNOWN"
            base_score = TIER_WEIGHTS.get(tier, TIER_WEIGHTS["UNKNOWN"])

            attempted = int(match.stats_attempt_count or 0)
            attempt_penalty = min(attempted * 0.15, 0.45)

            odds_bonus = 0.10 if bool(match.has_odds) else 0.0

            score = base_score + odds_bonus - attempt_penalty

            scored.append(
                {
                    "score": score,
                    "match": match,
                }
            )

        scored.sort(
            key=lambda item: (
                -float(item["score"]),
                item["match"].kickoff_date,
                item["match"].id,
            )
        )

        selected = []
        per_league: dict[str, int] = defaultdict(int)

        for item in scored:
            match = item["match"]
            league = match.league or "UNKNOWN"

            if per_league[league] >= MAX_MATCHES_PER_LEAGUE:
                continue

            selected.append(match)
            per_league[league] += 1

            if len(selected) >= self.limit:
                break

        return selected

    def _load_league_stats_scores(self) -> dict[tuple[str, int | None], dict[str, Any]]:
        rows = self.session.execute(
            text(
                """
                SELECT
                    m.league,
                    m.season,
                    COUNT(*) FILTER (WHERE m.is_finished = true) AS finished_matches,
                    COUNT(DISTINCT tms.match_id) FILTER (WHERE tms.is_real = true) AS real_stats_matches,
                    COUNT(*) FILTER (WHERE m.stats_attempt_count > 0) AS attempted_matches,
                    COUNT(*) FILTER (WHERE m.stats_unavailable = true) AS unavailable_matches
                FROM matches m
                LEFT JOIN team_match_stats tms ON tms.match_id = m.id
                WHERE m.provider = 'api-football'
                  AND m.league IS NOT NULL
                  AND m.is_cancelled = false
                  AND m.is_postponed = false
                GROUP BY m.league, m.season
                """
            )
        ).mappings().all()

        output: dict[tuple[str, int | None], dict[str, Any]] = {}

        for row in rows:
            finished = int(row["finished_matches"] or 0)
            real_stats = int(row["real_stats_matches"] or 0)
            attempted = int(row["attempted_matches"] or 0)
            unavailable = int(row["unavailable_matches"] or 0)

            coverage_rate = real_stats / finished if finished else 0.0
            success_rate = real_stats / attempted if attempted else 0.0
            unavailable_rate = unavailable / attempted if attempted else 0.0

            score = (
                coverage_rate * 0.45
                + success_rate * 0.40
                + max(0.0, 1.0 - unavailable_rate) * 0.15
            )

            if score >= 0.70:
                tier = "STRONG_STATS_COVERAGE"
            elif score >= 0.45:
                tier = "USABLE_STATS_COVERAGE"
            elif score >= 0.20:
                tier = "LIMITED_STATS_COVERAGE"
            else:
                tier = "POOR_STATS_COVERAGE"

            output[(row["league"], row["season"])] = {
                "tier": tier,
                "score": round(score, 4),
                "coverage_rate": round(coverage_rate, 4),
                "success_rate": round(success_rate, 4),
                "unavailable_rate": round(unavailable_rate, 4),
            }

        return output