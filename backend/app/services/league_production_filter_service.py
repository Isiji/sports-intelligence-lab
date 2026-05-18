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

CONDITIONAL_ALLOWED_TIERS = {
    "LIMITED_ODDS_COVERAGE",
}

BLOCKED_TIERS = {
    "POOR_ODDS_COVERAGE",
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


def _float_value(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_strong_exact_executable_candidate(candidate: dict[str, Any]) -> bool:
    """
    Allows only high-quality exact executable picks from LIMITED coverage leagues.

    This does NOT allow poor leagues.
    This is mainly for newer executable markets like Asian handicap where:
    - odds are exact
    - confidence is strong
    - value is strong
    - bookmaker/source exists
    """

    odds_quality = str(candidate.get("odds_match_quality") or "")
    bookmaker = candidate.get("odds_bookmaker")
    confidence = _float_value(candidate.get("confidence"))
    value_score = _float_value(candidate.get("value_score"))
    odds = _float_value(candidate.get("odds"))

    if odds_quality != "exact_executable_market":
        return False

    if not bookmaker:
        return False

    if confidence < 0.64:
        return False

    if value_score < 0.06:
        return False

    if odds < 1.30 or odds > 4.20:
        return False

    return True


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


def _get_league_snapshot(
    session: Session,
    league: str | None,
    sport: str,
) -> LeagueOddsCoverageSnapshot | None:
    if not league:
        return None

    return session.scalar(
        select(LeagueOddsCoverageSnapshot).where(
            LeagueOddsCoverageSnapshot.sport == sport,
            LeagueOddsCoverageSnapshot.league == league,
        )
    )


def filter_candidate_dicts_by_league_quality(
    session: Session,
    candidates: list[dict],
    mode: str = "strict",
    allowed_tiers: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    mode:
    - strict: block poor/non-production leagues, but conditionally allow strong exact executable picks from LIMITED leagues
    - advisory: log non-production leagues but allow them
    - off: skip league odds filtering
    """

    mode = (mode or "strict").lower().strip()

    if allowed_tiers is None:
        allowed_tiers = DEFAULT_ALLOWED_TIERS

    if mode == "off":
        return candidates, []

    approved: list[dict] = []
    rejected: list[dict] = []

    for candidate in candidates:
        kickoff_time = _format_kickoff_time(candidate)

        if kickoff_time:
            candidate["kickoff_time"] = kickoff_time

        league = candidate.get("league")
        sport = candidate.get("sport") or "football"

        snapshot = _get_league_snapshot(
            session=session,
            league=league,
            sport=sport,
        )

        coverage_tier = snapshot.coverage_tier if snapshot else None
        production_allowed = bool(snapshot.production_allowed) if snapshot else False

        reason = "league_allowed"
        allowed = True

        if not league:
            allowed = False
            reason = "missing_league"

        elif snapshot is None:
            allowed = False
            reason = "league_coverage_missing"

        elif snapshot.production_allowed is not True:
            allowed = False
            reason = snapshot.reason or "production_not_allowed"

        elif coverage_tier in allowed_tiers:
            allowed = True
            reason = "league_allowed"

        elif coverage_tier in CONDITIONAL_ALLOWED_TIERS and _is_strong_exact_executable_candidate(candidate):
            allowed = True
            reason = f"conditional_exact_executable_allowed:{coverage_tier}"
            candidate["league_quality_warning"] = f"conditional_limited_tier:{coverage_tier}"

        elif coverage_tier in BLOCKED_TIERS:
            allowed = False
            reason = f"blocked_tier:{coverage_tier}"

        else:
            allowed = False
            reason = f"blocked_tier:{coverage_tier}"

        rejection = {
            "prediction_id": candidate.get("prediction_id"),
            "match_id": candidate.get("match_id"),
            "league": league,
            "home_team": candidate.get("home_team"),
            "away_team": candidate.get("away_team"),
            "kickoff_time": kickoff_time,
            "market": candidate.get("market"),
            "predicted_label": candidate.get("predicted_label"),
            "coverage_tier": coverage_tier,
            "production_allowed": production_allowed,
            "reason": reason,
            "mode": mode,
        }

        if allowed:
            candidate["league_coverage_tier"] = coverage_tier
            candidate["league_quality_reason"] = reason
            approved.append(candidate)
            continue

        rejected.append(rejection)

        if mode == "advisory":
            candidate["league_quality_warning"] = reason
            candidate["league_coverage_tier"] = coverage_tier
            candidate["league_quality_reason"] = reason
            approved.append(candidate)

    return approved, rejected