# backend/app/odds/market_parser.py

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.odds.canonical_markets import is_supported_market


@dataclass(frozen=True)
class NormalizedOddsResult:
    canonical_market: str | None
    reason: str
    confidence: float
    market_family: str | None = None
    market_scope: str | None = None
    team_scope: str | None = None
    line_value: float | None = None
    metadata: dict[str, Any] | None = None


def clean_text(value: str | None) -> str:
    if not value:
        return ""

    value = str(value).lower().strip()
    value = value.replace("-", " ")
    value = value.replace("_", " ")
    value = value.replace("/", " ")
    value = re.sub(r"\s+", " ", value)

    return value


def compact_key(value: str | None) -> str:
    return clean_text(value).replace(" ", "_")


def normalize_direct_market(value: str | None) -> str | None:
    key = compact_key(value)

    if is_supported_market(key):
        return key

    if key.startswith("over_") and not key.endswith("_goals"):
        candidate = f"{key}_goals"
        if is_supported_market(candidate):
            return candidate

    if key.startswith("under_") and not key.endswith("_goals"):
        candidate = f"{key}_goals"
        if is_supported_market(candidate):
            return candidate

    return None


def extract_line(text: str) -> float | None:
    match = re.search(
        r"(?<!\d)(0(?:\.|_)?5|1(?:\.|_)?5|2(?:\.|_)?5|3(?:\.|_)?5|4(?:\.|_)?5|5(?:\.|_)?5|6(?:\.|_)?5|7(?:\.|_)?5|8(?:\.|_)?5|9(?:\.|_)?5|10(?:\.|_)?5|11(?:\.|_)?5)(?!\d)",
        text,
    )

    if not match:
        return None

    return float(match.group(1).replace("_", "."))


def line_to_key(line: float) -> str:
    return str(line).replace(".", "_")


def _result(
    canonical_market: str | None,
    reason: str,
    confidence: float,
    market_family: str | None = None,
    market_scope: str | None = None,
    team_scope: str | None = None,
    line_value: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> NormalizedOddsResult:
    return NormalizedOddsResult(
        canonical_market=canonical_market,
        reason=reason,
        confidence=confidence,
        market_family=market_family,
        market_scope=market_scope,
        team_scope=team_scope,
        line_value=line_value,
        metadata=metadata or {},
    )


def normalize_market_and_selection(
    market_name: str | None,
    selection_name: str | None,
    home_team: str | None = None,
    away_team: str | None = None,
) -> NormalizedOddsResult:
    direct = (
        normalize_direct_market(selection_name)
        or normalize_direct_market(market_name)
    )

    if direct:
        return _result(
            canonical_market=direct,
            reason="already_canonical",
            confidence=1.0,
            market_family=detect_market_family(direct),
            market_scope=detect_market_scope(direct),
            team_scope=detect_team_scope(direct),
            line_value=extract_line(direct),
        )

    market = clean_text(market_name)
    selection = clean_text(selection_name)
    home = clean_text(home_team)
    away = clean_text(away_team)
    combined = f"{market} {selection}".strip()

    # Match winner / 1X2
    if any(
        x in market
        for x in [
            "match winner",
            "winner",
            "1x2",
            "fulltime result",
            "full time result",
            "match result",
        ]
    ):
        if selection in ["home", "1", "team 1"] or selection == home:
            return _result("home_win", "match_winner_home", 0.98, "MATCH_RESULT", "FULL_TIME", "HOME")

        if selection in ["draw", "x"] or "draw" in selection:
            return _result("draw", "match_winner_draw", 0.98, "MATCH_RESULT", "FULL_TIME", None)

        if selection in ["away", "2", "team 2"] or selection == away:
            return _result("away_win", "match_winner_away", 0.98, "MATCH_RESULT", "FULL_TIME", "AWAY")

    # Double chance
    if "double chance" in market or market in ["dc"]:
        if selection in ["1x", "1 x", "home draw", "home or draw"]:
            return _result("double_chance_1x", "double_chance_1x", 0.99, "DOUBLE_CHANCE", "FULL_TIME")

        if selection in ["x2", "x 2", "draw away", "draw or away"]:
            return _result("double_chance_x2", "double_chance_x2", 0.99, "DOUBLE_CHANCE", "FULL_TIME")

        if selection in ["12", "1 2", "home away", "home or away"]:
            return _result("double_chance_12", "double_chance_12", 0.99, "DOUBLE_CHANCE", "FULL_TIME")

    # BTTS
    if (
        "both teams score" in market
        or "both teams to score" in market
        or "btts" in market
        or "both team score" in market
    ):
        if selection in ["yes", "y"]:
            return _result("btts_yes", "btts_yes", 0.99, "BTTS", "FULL_TIME")

        if selection in ["no", "n"]:
            return _result("btts_no", "btts_no", 0.99, "BTTS", "FULL_TIME")

    # Full-time goals over/under
    goal_result = _normalize_total_goals(
        market=market,
        selection=selection,
        combined=combined,
        scope="FULL_TIME",
        prefix="",
        reason_prefix="goals",
    )
    if goal_result.canonical_market:
        return goal_result

    # First-half goals
    first_half_result = _normalize_total_goals(
        market=market,
        selection=selection,
        combined=combined,
        scope="FIRST_HALF",
        prefix="first_half_",
        reason_prefix="first_half_goals",
    )
    if first_half_result.canonical_market:
        return first_half_result

    # Second-half goals
    second_half_result = _normalize_total_goals(
        market=market,
        selection=selection,
        combined=combined,
        scope="SECOND_HALF",
        prefix="second_half_",
        reason_prefix="second_half_goals",
    )
    if second_half_result.canonical_market:
        return second_half_result

    # Corners
    corners_result = _normalize_corners(
        market=market,
        selection=selection,
        combined=combined,
    )
    if corners_result.canonical_market:
        return corners_result

    # Team totals
    team_total_result = _normalize_team_totals(
        market=market,
        selection=selection,
        combined=combined,
        home=home,
        away=away,
    )
    if team_total_result.canonical_market:
        return team_total_result

    # Asian handicap
    asian_result = _normalize_asian_handicap(
        market=market,
        selection=selection,
        combined=combined,
        home=home,
        away=away,
    )
    if asian_result.canonical_market:
        return asian_result

    return _result(
        None,
        "unsupported_or_unmatched_market",
        0.0,
        metadata={
            "market": market,
            "selection": selection,
        },
    )


def _normalize_total_goals(
    market: str,
    selection: str,
    combined: str,
    scope: str,
    prefix: str,
    reason_prefix: str,
) -> NormalizedOddsResult:
    scope_markers = {
        "FULL_TIME": ["goals over under", "over under", "total goals", "goals total", "total"],
        "FIRST_HALF": ["first half", "1st half", "1st period", "half time"],
        "SECOND_HALF": ["second half", "2nd half", "2nd period"],
    }

    if scope == "FULL_TIME":
        is_scope = any(x in market for x in scope_markers["FULL_TIME"])
    else:
        is_scope = any(x in market or x in combined for x in scope_markers[scope])

    if not is_scope:
        return _result(None, "not_total_goals", 0.0)

    line = extract_line(combined)

    if line is None:
        return _result(None, "missing_goal_line", 0.0)

    normalized_line = line_to_key(line)

    if "over" in selection or "over" in combined:
        key = f"{prefix}over_{normalized_line}_goals"
        alt_key = f"{prefix}over_{normalized_line}"

        canonical = key if is_supported_market(key) else alt_key if is_supported_market(alt_key) else None

        if canonical:
            return _result(
                canonical,
                f"{reason_prefix}_over_{line}",
                0.98,
                "GOALS",
                scope,
                None,
                line,
            )

    if "under" in selection or "under" in combined:
        key = f"{prefix}under_{normalized_line}_goals"
        alt_key = f"{prefix}under_{normalized_line}"

        canonical = key if is_supported_market(key) else alt_key if is_supported_market(alt_key) else None

        if canonical:
            return _result(
                canonical,
                f"{reason_prefix}_under_{line}",
                0.98,
                "GOALS",
                scope,
                None,
                line,
            )

    return _result(None, "total_goals_unmatched_direction", 0.0)


def _normalize_corners(
    market: str,
    selection: str,
    combined: str,
) -> NormalizedOddsResult:
    if "corner" not in combined:
        return _result(None, "not_corners", 0.0)

    line = extract_line(combined)

    if line is None:
        return _result(None, "missing_corners_line", 0.0)

    normalized_line = line_to_key(line)

    if "over" in selection or "over" in combined:
        key = f"corners_over_{normalized_line}"
        if is_supported_market(key):
            return _result(key, f"corners_over_{line}", 0.98, "CORNERS", "FULL_TIME", None, line)

    if "under" in selection or "under" in combined:
        key = f"corners_under_{normalized_line}"
        if is_supported_market(key):
            return _result(key, f"corners_under_{line}", 0.98, "CORNERS", "FULL_TIME", None, line)

    return _result(None, "corners_unmatched_direction", 0.0)


def _normalize_team_totals(
    market: str,
    selection: str,
    combined: str,
    home: str,
    away: str,
) -> NormalizedOddsResult:
    if not any(x in combined for x in ["team total", "home total", "away total", "home goals", "away goals"]):
        return _result(None, "not_team_total", 0.0)

    line = extract_line(combined)

    if line is None:
        return _result(None, "missing_team_total_line", 0.0)

    normalized_line = line_to_key(line)

    team_scope = None

    if "home" in combined or home and home in combined:
        team_scope = "home"
    elif "away" in combined or away and away in combined:
        team_scope = "away"

    if not team_scope:
        return _result(None, "missing_team_total_scope", 0.0)

    if "over" in selection or "over" in combined:
        key = f"{team_scope}_over_{normalized_line}_goals"
        if is_supported_market(key):
            return _result(key, f"{team_scope}_team_total_over_{line}", 0.97, "TEAM_TOTAL", "FULL_TIME", team_scope.upper(), line)

    if "under" in selection or "under" in combined:
        key = f"{team_scope}_under_{normalized_line}_goals"
        if is_supported_market(key):
            return _result(key, f"{team_scope}_team_total_under_{line}", 0.97, "TEAM_TOTAL", "FULL_TIME", team_scope.upper(), line)

    return _result(None, "team_total_unmatched_direction", 0.0)


def _normalize_asian_handicap(
    market: str,
    selection: str,
    combined: str,
    home: str,
    away: str,
) -> NormalizedOddsResult:
    if "asian handicap" not in combined and "handicap" not in combined:
        return _result(None, "not_asian_handicap", 0.0)

    team_scope = None

    if "home" in selection or selection == home or home and home in selection:
        team_scope = "home"
    elif "away" in selection or selection == away or away and away in selection:
        team_scope = "away"

    if not team_scope:
        return _result(None, "missing_asian_team_scope", 0.0)

    handicap_match = re.search(
        r"([+-]?\d+(?:[._]\d+)?)",
        combined,
    )

    if not handicap_match:
        return _result(None, "missing_asian_line", 0.0)

    value = float(handicap_match.group(1).replace("_", "."))

    if value == 0:
        direction = "zero"
        line_key = "zero"
    elif value > 0:
        direction = "plus"
        line_key = line_to_key(abs(value))
    else:
        direction = "minus"
        line_key = line_to_key(abs(value))

    key = (
        f"asian_handicap_{team_scope}_{direction}"
        if direction == "zero"
        else f"asian_handicap_{team_scope}_{direction}_{line_key}"
    )

    if is_supported_market(key):
        return _result(
            key,
            f"asian_handicap_{team_scope}_{direction}_{line_key}",
            0.96,
            "ASIAN_HANDICAP",
            "FULL_TIME",
            team_scope.upper(),
            value,
        )

    return _result(None, "asian_handicap_unsupported_line", 0.0)


def detect_market_family(canonical_market: str | None) -> str | None:
    if not canonical_market:
        return None

    market = canonical_market.lower()

    if market in ["home_win", "away_win", "draw"]:
        return "MATCH_RESULT"

    if market.startswith("double_chance"):
        return "DOUBLE_CHANCE"

    if market.startswith("btts"):
        return "BTTS"

    if market.startswith("corners"):
        return "CORNERS"

    if market.startswith("asian_handicap"):
        return "ASIAN_HANDICAP"

    if market.startswith("exact_score"):
        return "EXACT_SCORE"

    if market.startswith("ht_ft"):
        return "HT_FT"

    if market.startswith("first_half") or market.startswith("second_half"):
        return "GOALS"

    if "over" in market or "under" in market:
        return "GOALS"

    return "OTHER"


def detect_market_scope(canonical_market: str | None) -> str | None:
    if not canonical_market:
        return None

    market = canonical_market.lower()

    if market.startswith("first_half"):
        return "FIRST_HALF"

    if market.startswith("second_half"):
        return "SECOND_HALF"

    return "FULL_TIME"


def detect_team_scope(canonical_market: str | None) -> str | None:
    if not canonical_market:
        return None

    market = canonical_market.lower()

    if market.startswith("home_") or "_home_" in market:
        return "HOME"

    if market.startswith("away_") or "_away_" in market:
        return "AWAY"

    return None