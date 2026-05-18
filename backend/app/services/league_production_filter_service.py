# backend/app/services/league_production_filter_service.py

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import LeagueOddsCoverageSnapshot


DEFAULT_ALLOWED_TIERS = {
    "ELITE_ODDS_COVERAGE",
    "STRONG_ODDS_COVERAGE",
    "USABLE_ODDS_COVERAGE",
}


def _format_kickoff_time(candidate: dict[str, Any]) -> str | None:
    kickoff = (
        candidate.get("kickoff_datetime")
        or candidate.get("kickoff_date")
        or candidate.get("match_kickoff")
        or candidate.get("kickoff_time")
    )

    if kickoff is None:
        return None

    if isinstance(kickoff, datetime):
        return kickoff.strftime("%Y-%m-%d %H:%M")

    if isinstance(kickoff, date):
        return kickoff.strftime("%Y-%m-%d")

    return str(kickoff)


def is_league_allowed_for_production(
    session: Session,
    league: str | None,
    sport: str = "football",
    allowed_tiers: set[str] | None = None,
) -> tuple[bool, str]:
    if allowed_tiers is None:
        allowed_tiers = DEFAULT_ALLOWED_TIERS

    if not league:
        return False, "missing_league"

    snapshot = session.scalar(
        select(LeagueOddsCoverageSnapshot).where(
            LeagueOddsCoverageSnapshot.sport == sport,
            LeagueOddsCoverageSnapshot.league == league,
        )
    )

    if snapshot is None:
        return False, "league_coverage_missing"

    if snapshot.production_allowed is not True:
        return False, snapshot.reason or "production_not_allowed"

    if snapshot.coverage_tier not in allowed_tiers:
        return False, f"blocked_tier:{snapshot.coverage_tier}"

    return True, "league_allowed"


def filter_candidate_dicts_by_league_quality(
    session: Session,
    candidates: list[dict],
    mode: str = "strict",
    allowed_tiers: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    mode:
    - strict: block non-production leagues
    - advisory: log non-production leagues but allow them
    - off: skip league odds filtering
    """

    mode = (mode or "strict").lower().strip()

    if mode == "off":
        return candidates, []

    approved: list[dict] = []
    rejected: list[dict] = []

    for candidate in candidates:
        kickoff_time = _format_kickoff_time(candidate)

        if kickoff_time:
            candidate["kickoff_time"] = kickoff_time

        allowed, reason = is_league_allowed_for_production(
            session=session,
            league=candidate.get("league"),
            sport=candidate.get("sport") or "football",
            allowed_tiers=allowed_tiers,
        )

        rejection = {
            "prediction_id": candidate.get("prediction_id"),
            "match_id": candidate.get("match_id"),
            "league": candidate.get("league"),
            "home_team": candidate.get("home_team"),
            "away_team": candidate.get("away_team"),
            "kickoff_time": kickoff_time,
            "market": candidate.get("market"),
            "predicted_label": candidate.get("predicted_label"),
            "reason": reason,
            "mode": mode,
        }

        if allowed:
            approved.append(candidate)
            continue

        rejected.append(rejection)

        if mode == "advisory":
            candidate["league_quality_warning"] = reason
            approved.append(candidate)

    return approved, rejected