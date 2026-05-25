# backend/app/odds/executable_market_registry.py

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExecutableMarketMetadata:
    canonical_market: str
    family: str
    scope: str
    side: str | None
    line: float | None
    derivative_type: str
    execution_risk: str
    volatility_tier: str
    bookmaker_rich: bool
    calibration_scope: str
    production_ready: bool
    metadata: dict[str, Any]


BOOKMAKER_RICH_FAMILIES = {
    "MATCH_RESULT",
    "DOUBLE_CHANCE",
    "GOALS_TOTAL",
    "FIRST_HALF_GOALS_TOTAL",
    "SECOND_HALF_GOALS_TOTAL",
    "BTTS",
    "ASIAN_HANDICAP",
    "FIRST_HALF_RESULT",
    "SECOND_HALF_RESULT",
    "DRAW_NO_BET",
    "TEAM_TOTAL",
    "CORNERS",
    "SHOTS_ON_TARGET",
}

LOW_RISK_FAMILIES = {
    "MATCH_RESULT",
    "DOUBLE_CHANCE",
    "GOALS_TOTAL",
    "BTTS",
}

MEDIUM_RISK_FAMILIES = {
    "FIRST_HALF_RESULT",
    "FIRST_HALF_GOALS_TOTAL",
    "SECOND_HALF_RESULT",
    "SECOND_HALF_GOALS_TOTAL",
    "ASIAN_HANDICAP",
    "TEAM_TOTAL",
    "CORNERS",
}

HIGH_RISK_FAMILIES = {
    "HT_FT",
    "EXACT_SCORE",
}

PRODUCTION_ENABLED_FAMILIES = {
    "MATCH_RESULT",
    "DOUBLE_CHANCE",
    "GOALS_TOTAL",
    "FIRST_HALF_GOALS_TOTAL",
    "SECOND_HALF_GOALS_TOTAL",
    "BTTS",
    "ASIAN_HANDICAP",
    "FIRST_HALF_RESULT",
    "SECOND_HALF_RESULT",
    "DRAW_NO_BET",
    "TEAM_TOTAL",
    "CORNERS",
    "SHOTS_ON_TARGET",
}

def parse_executable_market(
    canonical_market: str,
) -> ExecutableMarketMetadata:
    market = canonical_market.lower()

    family = resolve_family(market)
    scope = resolve_scope(market)
    side = resolve_side(market)
    line = resolve_line(market)

    derivative_type = resolve_derivative_type(family)

    execution_risk = resolve_execution_risk(family)

    volatility_tier = resolve_volatility_tier(family)

    bookmaker_rich = family in BOOKMAKER_RICH_FAMILIES

    production_ready = family in PRODUCTION_ENABLED_FAMILIES

    calibration_scope = build_calibration_scope(
        family=family,
        scope=scope,
    )

    return ExecutableMarketMetadata(
        canonical_market=canonical_market,
        family=family,
        scope=scope,
        side=side,
        line=line,
        derivative_type=derivative_type,
        execution_risk=execution_risk,
        volatility_tier=volatility_tier,
        bookmaker_rich=bookmaker_rich,
        calibration_scope=calibration_scope,
        production_ready=production_ready,
        metadata={
            "is_first_half": scope == "FIRST_HALF",
            "is_second_half": scope == "SECOND_HALF",
            "is_exact_score": family == "EXACT_SCORE",
            "is_handicap": family == "ASIAN_HANDICAP",
            "is_derivative": derivative_type != "binary",
        },
    )


def resolve_family(market: str) -> str:
    if market in {"home_win", "draw", "away_win"}:
        return "MATCH_RESULT"

    if market.startswith("double_chance"):
        return "DOUBLE_CHANCE"

    if market.startswith("draw_no_bet"):
        return "DRAW_NO_BET"

    if market.startswith("btts"):
        return "BTTS"

    if market.startswith("corners"):
        return "CORNERS"

    if market.startswith("shots_on_target"):
        return "SHOTS_ON_TARGET"

    if market.startswith("asian_handicap"):
        return "ASIAN_HANDICAP"

    if market.startswith("handicap_result"):
        return "HANDICAP_RESULT"

    if market.startswith("result_total"):
        return "RESULT_TOTAL"

    if market.startswith("home_away"):
        return "HOME_AWAY"

    if market.startswith("ht_ft"):
        return "HT_FT"

    if market.startswith("exact_score"):
        return "EXACT_SCORE"

    if market.startswith("first_half_double_chance"):
        return "FIRST_HALF_DOUBLE_CHANCE"

    if market.startswith("first_half_home"):
        return "FIRST_HALF_RESULT"

    if market.startswith("first_half_draw"):
        return "FIRST_HALF_RESULT"

    if market.startswith("first_half_away"):
        return "FIRST_HALF_RESULT"

    if market.startswith("second_half_home"):
        return "SECOND_HALF_RESULT"

    if market.startswith("second_half_draw"):
        return "SECOND_HALF_RESULT"

    if market.startswith("second_half_away"):
        return "SECOND_HALF_RESULT"

    if market.startswith("first_half") and (
        "over" in market or "under" in market
    ):
        return "FIRST_HALF_GOALS_TOTAL"

    if market.startswith("second_half") and (
        "over" in market or "under" in market
    ):
        return "SECOND_HALF_GOALS_TOTAL"

    if (
        market.startswith("home_")
        or market.startswith("away_")
    ) and (
        "over" in market or "under" in market
    ):
        return "TEAM_TOTAL"

    if "over" in market or "under" in market:
        return "GOALS_TOTAL"

    return "OTHER"

def resolve_scope(market: str) -> str:
    if market.startswith("first_half"):
        return "FIRST_HALF"

    if market.startswith("second_half"):
        return "SECOND_HALF"

    return "FULL_TIME"


def resolve_side(market: str) -> str | None:
    if (
        market.startswith("home_")
        or "_home_" in market
    ):
        return "HOME"

    if (
        market.startswith("away_")
        or "_away_" in market
    ):
        return "AWAY"

    return None

def is_local_realistic_market(
    canonical_market: str,
) -> bool:
    parsed = parse_executable_market(
        canonical_market
    )

    if parsed.family in {
        "MATCH_RESULT",
        "DOUBLE_CHANCE",
        "DRAW_NO_BET",
        "GOALS_TOTAL",
        "BTTS",
        "TEAM_TOTAL",
        "ASIAN_HANDICAP",
        "FIRST_HALF_GOALS_TOTAL",
        "FIRST_HALF_RESULT",
    }:
        return True

    return False

def resolve_line(market: str) -> float | None:
    if "zero" in market:
        return 0.0

    match = re.search(
        r"(\d+_\d+)",
        market,
    )

    if not match:
        return None

    raw = match.group(1).replace("_", ".")

    try:
        value = float(raw)
    except Exception:
        return None

    if "minus" in market:
        value *= -1

    return value


def resolve_derivative_type(
    family: str,
) -> str:
    if family in {
        "MATCH_RESULT",
        "DOUBLE_CHANCE",
        "BTTS",
        "FIRST_HALF_RESULT",
        "SECOND_HALF_RESULT",
    }:
        return "binary"

    if family in {
        "GOALS_TOTAL",
        "FIRST_HALF_GOALS_TOTAL",
        "SECOND_HALF_GOALS_TOTAL",
        "TEAM_TOTAL",
        "CORNERS",
        "SHOTS_ON_TARGET",
    }:
        return "totals"

    if family == "ASIAN_HANDICAP":
        return "spread"

    if family == "HT_FT":
        return "sequence"

    if family == "EXACT_SCORE":
        return "distribution"

    return "other"


def resolve_execution_risk(
    family: str,
) -> str:
    if family in LOW_RISK_FAMILIES:
        return "LOW"

    if family in MEDIUM_RISK_FAMILIES:
        return "MEDIUM"

    if family in HIGH_RISK_FAMILIES:
        return "HIGH"

    return "UNKNOWN"


def resolve_volatility_tier(
    family: str,
) -> str:
    if family in {
        "MATCH_RESULT",
        "DOUBLE_CHANCE",
        "BTTS",
    }:
        return "LOW"

    if family in {
        "GOALS_TOTAL",
        "FIRST_HALF_GOALS_TOTAL",
        "SECOND_HALF_GOALS_TOTAL",
        "ASIAN_HANDICAP",
    }:
        return "MEDIUM"

    if family in {
        "HT_FT",
        "EXACT_SCORE",
    }:
        return "EXTREME"

    return "HIGH"


def build_calibration_scope(
    family: str,
    scope: str,
) -> str:
    return f"{family}_{scope}"


def is_production_ready_market(
    canonical_market: str,
) -> bool:
    parsed = parse_executable_market(canonical_market)

    return parsed.production_ready


def get_market_family(
    canonical_market: str,
) -> str:
    return parse_executable_market(
        canonical_market
    ).family


def get_market_scope(
    canonical_market: str,
) -> str:
    return parse_executable_market(
        canonical_market
    ).scope


def get_market_side(
    canonical_market: str,
) -> str | None:
    return parse_executable_market(
        canonical_market
    ).side