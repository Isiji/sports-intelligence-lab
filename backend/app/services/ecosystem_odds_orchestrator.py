# backend/app/services/ecosystem_odds_orchestrator.py

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from app.db.models import Match
from app.ingest.football_odds_ingestion import ingest_odds_for_fixture
from app.services.league_cooldown_service import LeagueCooldownService


PRIORITY_WEIGHTS = {
    "CORE_PRODUCTION": 1.35,
    "HIGH_PRIORITY": 1.15,
    "GROWTH_PRIORITY": 0.90,
    "EXPLORATION_PRIORITY": 0.48,
    "DISCOVERY_ROTATION": 0.10,
}


TOURNAMENT_STAGE_WEIGHTS = {
    "final": 0.70,
    "semifinal": 0.55,
    "quarterfinal": 0.42,
    "round_of_16": 0.30,
    "knockout": 0.25,
    "group_stage": 0.12,
    "qualifier": 0.18,
    "playoff": 0.22,
}


TOURNAMENT_TYPE_WEIGHTS = {
    "world_cup": 0.60,
    "continental_cup": 0.42,
    "continental_qualifier": 0.30,
    "international": 0.22,
    "domestic_cup": 0.18,
    "league": 0.0,
    None: 0.0,
}


class EcosystemOddsOrchestrator:
    """
    Adaptive ecosystem odds orchestration.

    Production-safe defaults:
    - fast retries for odds
    - short cooldowns
    - season-aware
    - league-aware
    - recency-aware
    - no permanent league exclusion
    - avoids old finished-match API waste
    - tournament-aware prioritization
    """

    def __init__(
        self,
        session: Session,
        limit: int = 500,
        season: int | None = None,
        mode: str = "ecosystem",
        leagues: list[str] | None = None,
        force: bool = False,
        use_league_cooldown: bool = True,
        odds_window_hours: int = 72,
        require_stats_for_finished: bool = True,
        max_age_days: int = 14,
        recent_hours: int | None = None,
    ):
        self.session = session
        self.limit = int(limit)
        self.season = season
        self.mode = (mode or "ecosystem").lower().strip()

        self.leagues = [
            league.strip()
            for league in (leagues or [])
            if league.strip()
        ]

        self.force = force
        self.use_league_cooldown = use_league_cooldown
        self.odds_window_hours = int(odds_window_hours)
        self.require_stats_for_finished = require_stats_for_finished
        self.max_age_days = int(max_age_days)
        self.recent_hours = recent_hours

        self.cooldown_service = LeagueCooldownService(
            session=session,
            lookback_days=2,
            min_attempts=5,
        )

    def run(self) -> dict:
        matches = self._select_candidate_matches()

        processed = 0
        failed = 0
        skipped_by_cooldown = 0
        failures = []
        sample_results = []

        for match in matches:
            try:
                snapshot = self._resolve_league_snapshot(match.league)

                cooldown_status = self.cooldown_service.get_league_cooldown_status(
                    match.league,
                    data_type="odds",
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
                            "season": match.season,
                            "mode": self.mode,
                            "priority_tier": snapshot["priority_tier"],
                            "ecosystem_score": snapshot["ecosystem_score"],
                            "coverage_score": snapshot["coverage_score"],
                            "bookmaker_count": snapshot["bookmaker_count"],
                            "supported_market_count": snapshot["supported_market_count"],
                            "competition_priority": getattr(
                                match,
                                "competition_priority",
                                None,
                            ),
                            "tournament_type": getattr(
                                match,
                                "tournament_type",
                                None,
                            ),
                            "tournament_stage": getattr(
                                match,
                                "tournament_stage",
                                None,
                            ),
                            "tournament_pressure_score": getattr(
                                match,
                                "tournament_pressure_score",
                                None,
                            ),
                            "cooldown": cooldown_status,
                            "home_team": match.home_team,
                            "away_team": match.away_team,
                            "kickoff_datetime": str(match.kickoff_datetime),
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
                            "home_team": match.home_team,
                            "away_team": match.away_team,
                            "error": str(exc),
                        }
                    )

        return {
            "mode": self.mode,
            "season": self.season,
            "leagues": self.leagues,
            "limit": self.limit,
            "odds_window_hours": self.odds_window_hours,
            "max_age_days": self.max_age_days,
            "recent_hours": self.recent_hours,
            "require_stats_for_finished": self.require_stats_for_finished,
            "matches_selected": len(matches),
            "matches_processed": processed,
            "matches_skipped_by_cooldown": skipped_by_cooldown,
            "matches_failed": failed,
            "failures": failures,
            "sample_results": sample_results,
        }

    def _select_candidate_matches(self) -> list[Match]:
        now = datetime.utcnow()

        cooldown_filter = self._build_short_retry_filter(now)

        query = (
            select(Match)
            .where(Match.provider_fixture_id.is_not(None))
            .where(Match.is_cancelled == False)
            .where(Match.is_postponed == False)
            .where(Match.has_odds == False)
            .where(cooldown_filter)
        )

        if self.season is not None:
            query = query.where(Match.season == self.season)

        if self.leagues:
            query = query.where(Match.league.in_(self.leagues))

        if self.mode in ["ecosystem", "upcoming"]:
            max_window = now + timedelta(hours=self.odds_window_hours)

            query = (
                query.where(Match.is_finished == False)
                .where(Match.kickoff_datetime.is_not(None))
                .where(Match.kickoff_datetime >= now)
                .where(Match.kickoff_datetime <= max_window)
            )

        elif self.mode == "finished":
            query = self._apply_finished_filters(query, now)

        elif self.mode == "season":
            query = (
                query.where(Match.is_finished == True)
                .where(Match.home_goals.is_not(None))
                .where(Match.away_goals.is_not(None))
            )

            if self.require_stats_for_finished:
                query = query.where(Match.has_stats == True)

        elif self.mode == "all":
            upcoming_window = now + timedelta(hours=self.odds_window_hours)
            finished_cutoff = now - timedelta(days=self.max_age_days)

            query = query.where(
                or_(
                    and_(
                        Match.is_finished == False,
                        Match.kickoff_datetime.is_not(None),
                        Match.kickoff_datetime >= now,
                        Match.kickoff_datetime <= upcoming_window,
                    ),
                    and_(
                        Match.is_finished == True,
                        Match.home_goals.is_not(None),
                        Match.away_goals.is_not(None),
                        Match.kickoff_datetime.is_not(None),
                        Match.kickoff_datetime >= finished_cutoff,
                    ),
                )
            )

            if self.require_stats_for_finished:
                query = query.where(
                    or_(
                        Match.is_finished == False,
                        Match.has_stats == True,
                    )
                )

        else:
            raise ValueError(
                "Invalid mode. Use ecosystem, upcoming, finished, season, or all."
            )

        query = query.order_by(
            Match.kickoff_datetime.asc().nulls_last(),
            Match.id.asc(),
        ).limit(self.limit * 20)

        candidates = list(self.session.scalars(query))

        scored = self._score_candidates(
            candidates=candidates,
            now=now,
        )

        return self._select_balanced_matches(scored)

    def _apply_finished_filters(self, query, now: datetime):
        query = (
            query.where(Match.is_finished == True)
            .where(Match.home_goals.is_not(None))
            .where(Match.away_goals.is_not(None))
        )

        if self.require_stats_for_finished:
            query = query.where(Match.has_stats == True)

        if self.recent_hours is not None:
            cutoff = now - timedelta(hours=int(self.recent_hours))
            query = query.where(Match.kickoff_datetime >= cutoff)

        elif self.max_age_days > 0:
            cutoff = now - timedelta(days=self.max_age_days)
            query = query.where(Match.kickoff_datetime >= cutoff)

        return query

    def _build_short_retry_filter(self, now: datetime):
        return or_(
            Match.odds_unavailable == False,
            Match.odds_attempt_count == 0,
            and_(
                Match.odds_unavailable == True,
                Match.odds_attempt_count < 3,
                Match.kickoff_datetime.is_not(None),
                Match.kickoff_datetime >= now,
                Match.kickoff_datetime <= now + timedelta(hours=24),
                Match.odds_attempted_at < func.now() - text("INTERVAL '30 minutes'"),
            ),
            and_(
                Match.odds_unavailable == True,
                Match.odds_attempt_count < 3,
                Match.kickoff_datetime.is_not(None),
                Match.kickoff_datetime > now + timedelta(hours=24),
                Match.kickoff_datetime <= now + timedelta(hours=72),
                Match.odds_attempted_at < func.now() - text("INTERVAL '1 hour'"),
            ),
            and_(
                Match.odds_unavailable == True,
                Match.odds_attempt_count < 3,
                Match.is_finished == True,
                Match.odds_attempted_at < func.now() - text("INTERVAL '3 hours'"),
            ),
            and_(
                Match.odds_unavailable == True,
                Match.odds_attempt_count < 2,
                Match.is_finished == True,
                Match.kickoff_datetime.is_not(None),
                Match.kickoff_datetime >= now - timedelta(days=self.max_age_days),
                Match.odds_attempted_at < func.now() - text("INTERVAL '6 hours'"),
            ),
        )

    def _score_candidates(
        self,
        candidates: list[Match],
        now: datetime,
    ) -> list[dict]:
        scored = []

        for match in candidates:
            snapshot = self._resolve_league_snapshot(match.league)

            priority_weight = PRIORITY_WEIGHTS.get(
                snapshot["priority_tier"],
                PRIORITY_WEIGHTS["DISCOVERY_ROTATION"],
            )

            attempt_penalty = min(
                float(match.odds_attempt_count or 0) * 0.10,
                0.35,
            )

            maturity_bonus = min(
                float(snapshot["ecosystem_score"] or 0.0) / 100.0,
                1.0,
            ) * 0.35

            bookmaker_bonus = min(
                float(snapshot["bookmaker_count"] or 0) / 12.0,
                1.0,
            ) * 0.15

            market_bonus = min(
                float(snapshot["supported_market_count"] or 0) / 250.0,
                1.0,
            ) * 0.12

            freshness_bonus = self._freshness_bonus(match, now)
            urgency_bonus = self._urgency_bonus(match, now)

            tournament_bonus = self._tournament_bonus(match)
            pressure_bonus = self._pressure_bonus(match)
            international_bonus = self._international_bonus(match)

            league_adjustment = 0.0

            if self.use_league_cooldown and not self.force:
                cooldown_status = self.cooldown_service.get_league_cooldown_status(
                    match.league,
                    data_type="odds",
                )

                if cooldown_status["cooldown_active"]:
                    continue

                league_adjustment = self.cooldown_service.league_score_adjustment(
                    match.league,
                    data_type="odds",
                )

            score = (
                priority_weight
                + maturity_bonus
                + bookmaker_bonus
                + market_bonus
                + freshness_bonus
                + urgency_bonus
                + tournament_bonus
                + pressure_bonus
                + international_bonus
                + league_adjustment
                - attempt_penalty
            )

            scored.append(
                {
                    "score": score,
                    "priority_tier": snapshot["priority_tier"],
                    "match": match,
                }
            )

        scored.sort(
            key=lambda item: (
                item["score"],
                item["match"].kickoff_datetime or datetime.utcnow(),
            ),
            reverse=True,
        )

        return scored

    def _select_balanced_matches(self, scored: list[dict]) -> list[Match]:
        selected = []
        league_counts = defaultdict(int)

        for item in scored:
            match = item["match"]

            league_key = match.league or "UNKNOWN"

            tier = item["priority_tier"]

            league_limit = self._league_limit_for_tier(tier)

            if getattr(match, "is_international", False):
                league_limit += 2

            if getattr(match, "tournament_stage", None) in [
                "final",
                "semifinal",
                "quarterfinal",
            ]:
                league_limit += 2

            if self.mode in ["finished", "season"]:
                league_limit = max(league_limit, 10)

            if league_counts[league_key] >= league_limit:
                continue

            selected.append(match)

            league_counts[league_key] += 1

            if len(selected) >= self.limit:
                break

        return selected

    def _freshness_bonus(self, match: Match, now: datetime) -> float:
        if match.kickoff_datetime is None:
            return 0.0

        if match.is_finished:
            age_hours = (
                now - match.kickoff_datetime
            ).total_seconds() / 3600

            if age_hours <= 24:
                return 0.55

            if age_hours <= 72:
                return 0.35

            if age_hours <= 168:
                return 0.15

            return -0.25

        hours_to_kickoff = (
            match.kickoff_datetime - now
        ).total_seconds() / 3600

        if hours_to_kickoff <= 6:
            return 0.70

        if hours_to_kickoff <= 24:
            return 0.55

        if hours_to_kickoff <= 72:
            return 0.30

        return 0.0

    def _urgency_bonus(self, match: Match, now: datetime) -> float:
        if match.kickoff_datetime is None:
            return 0.0

        if match.is_finished:
            return 0.0

        hours_to_kickoff = (
            match.kickoff_datetime - now
        ).total_seconds() / 3600

        if 0 <= hours_to_kickoff <= 2:
            return 0.60

        if 0 <= hours_to_kickoff <= 6:
            return 0.45

        if 0 <= hours_to_kickoff <= 12:
            return 0.25

        return 0.0

    def _tournament_bonus(self, match: Match) -> float:
        tournament_type = getattr(match, "tournament_type", None)
        tournament_stage = getattr(match, "tournament_stage", None)

        type_bonus = TOURNAMENT_TYPE_WEIGHTS.get(
            tournament_type,
            0.0,
        )

        stage_bonus = TOURNAMENT_STAGE_WEIGHTS.get(
            tournament_stage,
            0.0,
        )

        return type_bonus + stage_bonus

    def _pressure_bonus(self, match: Match) -> float:
        pressure = float(
            getattr(match, "tournament_pressure_score", 0.0) or 0.0
        )

        return min(pressure, 1.0) * 0.35

    def _international_bonus(self, match: Match) -> float:
        if getattr(match, "is_international", False):
            return 0.20

        return 0.0

    def _league_limit_for_tier(self, priority_tier: str) -> int:
        if priority_tier == "CORE_PRODUCTION":
            return 10

        if priority_tier == "HIGH_PRIORITY":
            return 8

        if priority_tier == "GROWTH_PRIORITY":
            return 6

        if priority_tier == "EXPLORATION_PRIORITY":
            return 3

        return 2

    def _resolve_league_snapshot(self, league: str | None) -> dict:
        if not league:
            return self._default_snapshot()

        row = (
            self.session.execute(
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
                {"league": league},
            )
            .mappings()
            .first()
        )

        if not row:
            return self._default_snapshot()

        return {
            "priority_tier": row["priority_tier"] or "DISCOVERY_ROTATION",
            "ecosystem_score": float(row["ecosystem_score"] or 0.0),
            "coverage_score": float(row["coverage_score"] or 0.0),
            "bookmaker_count": int(row["bookmaker_count"] or 0),
            "supported_market_count": int(
                row["supported_market_count"] or 0
            ),
        }

    def _default_snapshot(self) -> dict:
        return {
            "priority_tier": "DISCOVERY_ROTATION",
            "ecosystem_score": 0.0,
            "coverage_score": 0.0,
            "bookmaker_count": 0,
            "supported_market_count": 0,
        }