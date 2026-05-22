# backend/app/services/odds_survivability_service.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.odds.executable_market_registry import (
    parse_executable_market,
)

UTC = timezone.utc


@dataclass(frozen=True)
class OddsSurvivabilityResult:
    survivability_score: float
    freshness_score: float
    persistence_score: float
    downgrade_risk_score: float
    stale: bool
    allowed: bool
    reasons: list[str]
    fallback_markets: list[str]


def _hours_since(
    value: datetime | None,
) -> float:

    if value is None:
        return 9999.0

    if value.tzinfo is None:
        value = value.replace(
            tzinfo=UTC
        )

    return max(
        (
            datetime.now(UTC)
            - value.astimezone(UTC)
        ).total_seconds()
        / 3600.0,
        0.0,
    )


def _fallback_markets(
    market: str,
) -> list[str]:

    if "asian_handicap_home" in market:
        return [
            "double_chance_1x",
            "draw_no_bet_home",
            "home_win",
            "over_1_5_goals",
            "btts_yes",
        ]

    if "asian_handicap_away" in market:
        return [
            "double_chance_x2",
            "draw_no_bet_away",
            "away_win",
            "over_1_5_goals",
            "btts_yes",
        ]

    if "asian_handicap" in market:
        return [
            "double_chance_1x",
            "double_chance_x2",
            "draw_no_bet_home",
            "draw_no_bet_away",
            "over_1_5_goals",
            "btts_yes",
        ]

    if "corners_" in market:
        return [
            "over_1_5_goals",
            "btts_yes",
        ]

    if "shots_on_target_" in market:
        return [
            "over_1_5_goals",
            "btts_yes",
        ]

    if market in {
        "home_win",
        "away_win",
        "draw",
    }:
        return [
            "double_chance_1x",
            "double_chance_x2",
            "draw_no_bet_home",
            "draw_no_bet_away",
        ]

    return []


def _freshness_score_for_age(
    age_hours: float,
    *,
    minutes_to_kickoff: int | None,
) -> tuple[float, list[str]]:

    reasons: list[str] = []

    if age_hours >= 24:
        reasons.append(
            "very stale odds"
        )
        return 0.05, reasons

    if age_hours >= 12:
        reasons.append(
            "stale odds"
        )
        return 0.20, reasons

    if age_hours >= 6:
        reasons.append(
            "aging odds"
        )
        return 0.45, reasons

    if age_hours >= 2:
        return 0.75, reasons

    if (
        minutes_to_kickoff is not None
        and minutes_to_kickoff <= 45
        and age_hours >= 1
    ):
        reasons.append(
            "late-window odds need refresh"
        )
        return 0.62, reasons

    return 1.0, reasons


def evaluate_odds_survivability(
    *,
    market: str,
    bookmaker: str | None,
    odds_retrieved_at: datetime | None,
    minutes_to_kickoff: int | None,
) -> OddsSurvivabilityResult:

    executable = parse_executable_market(
        market
    )

    reasons: list[str] = []

    age_hours = _hours_since(
        odds_retrieved_at
    )

    freshness_score, freshness_reasons = (
        _freshness_score_for_age(
            age_hours,
            minutes_to_kickoff=minutes_to_kickoff,
        )
    )

    reasons.extend(
        freshness_reasons
    )

    persistence_score = 1.0

    if not bookmaker:
        persistence_score = 0.30
        reasons.append(
            "missing bookmaker"
        )

    downgrade_risk_score = 0.0

    if executable.family == "ASIAN_HANDICAP":
        downgrade_risk_score += 0.45
        reasons.append(
            "asian handicap volatility"
        )

    if executable.family in {
        "CORNERS",
        "SHOTS_ON_TARGET",
    }:
        downgrade_risk_score += 0.20
        reasons.append(
            "special market volatility"
        )

    if executable.volatility_tier == "HIGH":
        downgrade_risk_score += 0.20
        reasons.append(
            "high volatility market"
        )

    elif executable.volatility_tier == "EXTREME":
        downgrade_risk_score += 0.40
        reasons.append(
            "extreme volatility market"
        )

    if minutes_to_kickoff is not None:

        if minutes_to_kickoff <= 8:
            downgrade_risk_score += 0.55
            freshness_score = min(
                freshness_score,
                0.35,
            )
            reasons.append(
                "too close to kickoff"
            )

        elif minutes_to_kickoff <= 15:
            downgrade_risk_score += 0.40
            reasons.append(
                "late market movement"
            )

        elif minutes_to_kickoff <= 45:
            downgrade_risk_score += 0.25
            reasons.append(
                "late execution window"
            )

        elif minutes_to_kickoff <= 120:
            downgrade_risk_score += 0.08

    downgrade_risk_score = min(
        downgrade_risk_score,
        1.0,
    )

    survivability_score = max(
        (
            freshness_score * 0.45
            + persistence_score * 0.35
            + (1.0 - downgrade_risk_score)
            * 0.20
        ),
        0.0,
    )

    stale = age_hours >= 72

    allowed = (
        survivability_score >= 0.25
        and downgrade_risk_score <= 0.90
    )
    
    if not allowed:
        reasons.append(
            "poor survivability"
        )

    return OddsSurvivabilityResult(
        survivability_score=round(
            survivability_score,
            4,
        ),
        freshness_score=round(
            freshness_score,
            4,
        ),
        persistence_score=round(
            persistence_score,
            4,
        ),
        downgrade_risk_score=round(
            downgrade_risk_score,
            4,
        ),
        stale=stale,
        allowed=allowed,
        reasons=reasons,
        fallback_markets=_fallback_markets(
            market
        ),
    )