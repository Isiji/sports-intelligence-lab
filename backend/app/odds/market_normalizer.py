# backend/app/odds/market_normalizer.py

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
    value = value.replace("&", " and ")
    value = value.replace("-", " ")
    value = value.replace("_", " ")
    value = value.replace("/", " ")
    value = re.sub(r"[^a-z0-9.+ ]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


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
    match = re.search(r"([+-]?\d+(?:[._]\d+)?)", text)
    if not match:
        return None
    return float(match.group(1).replace("_", "."))


def line_to_key(line: float) -> str:
    raw = f"{abs(line):.2f}".rstrip("0").rstrip(".")
    if "." not in raw:
        raw = f"{raw}.0"
    return raw.replace(".", "_")


def signed_line_to_key(line: float) -> str:
    if line < 0:
        return f"minus_{line_to_key(line)}"
    return f"plus_{line_to_key(line)}"


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
    direct = normalize_direct_market(selection_name) or normalize_direct_market(market_name)

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

    home_away = _normalize_home_away(market, selection)
    if home_away.canonical_market:
        return home_away

    match_result = _normalize_match_result(market, selection, home, away)
    if match_result.canonical_market:
        return match_result

    double_chance = _normalize_double_chance(market, selection)
    if double_chance.canonical_market:
        return double_chance

    first_half_double_chance = _normalize_first_half_double_chance(market, selection)
    if first_half_double_chance.canonical_market:
        return first_half_double_chance

    btts = _normalize_btts(market, selection)
    if btts.canonical_market:
        return btts

    result_total = _normalize_result_total_goals(market, selection)
    if result_total.canonical_market:
        return result_total

    handicap_result = _normalize_handicap_result(market, selection)
    if handicap_result.canonical_market:
        return handicap_result

    first_half_exact = _normalize_first_half_exact_score(market, selection)
    if first_half_exact.canonical_market:
        return first_half_exact

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

    corners_result = _normalize_corners(market, selection, combined)
    if corners_result.canonical_market:
        return corners_result

    team_total_result = _normalize_team_totals(market, selection, combined, home, away)
    if team_total_result.canonical_market:
        return team_total_result

    asian_result = _normalize_asian_handicap(market, selection, combined, home, away)
    if asian_result.canonical_market:
        return asian_result

    return _result(
        None,
        "unsupported_or_unmatched_market",
        0.0,
        metadata={"market": market, "selection": selection},
    )


def _normalize_home_away(market: str, selection: str) -> NormalizedOddsResult:
    if market != "home away":
        return _result(None, "not_home_away", 0.0)

    if selection in ["home", "1"]:
        return _result("home_away_home", "home_away_home", 0.92, "HOME_AWAY_2WAY", "FULL_TIME", "HOME")

    if selection in ["away", "2"]:
        return _result("home_away_away", "home_away_away", 0.92, "HOME_AWAY_2WAY", "FULL_TIME", "AWAY")

    return _result(None, "home_away_unmatched_selection", 0.0)


def _normalize_match_result(market: str, selection: str, home: str, away: str) -> NormalizedOddsResult:
    if not any(x in market for x in ["match winner", "winner", "1x2", "fulltime result", "full time result", "match result"]):
        return _result(None, "not_match_result", 0.0)

    if selection in ["home", "1", "team 1"] or selection == home:
        return _result("home_win", "match_winner_home", 0.98, "MATCH_RESULT", "FULL_TIME", "HOME")

    if selection in ["draw", "x"] or "draw" in selection:
        return _result("draw", "match_winner_draw", 0.98, "MATCH_RESULT", "FULL_TIME")

    if selection in ["away", "2", "team 2"] or selection == away:
        return _result("away_win", "match_winner_away", 0.98, "MATCH_RESULT", "FULL_TIME", "AWAY")

    return _result(None, "match_result_unmatched_selection", 0.0)


def _normalize_double_chance(market: str, selection: str) -> NormalizedOddsResult:
    if "double chance" not in market and market != "dc":
        return _result(None, "not_double_chance", 0.0)

    if "first half" in market or "1st half" in market:
        return _result(None, "double_chance_first_half_skip", 0.0)

    if selection in ["1x", "1 x", "home draw", "home or draw"]:
        return _result("double_chance_1x", "double_chance_1x", 0.99, "DOUBLE_CHANCE", "FULL_TIME")

    if selection in ["x2", "x 2", "draw away", "draw or away"]:
        return _result("double_chance_x2", "double_chance_x2", 0.99, "DOUBLE_CHANCE", "FULL_TIME")

    if selection in ["12", "1 2", "home away", "home or away"]:
        return _result("double_chance_12", "double_chance_12", 0.99, "DOUBLE_CHANCE", "FULL_TIME")

    return _result(None, "double_chance_unmatched_selection", 0.0)


def _normalize_first_half_double_chance(market: str, selection: str) -> NormalizedOddsResult:
    if "double chance" not in market:
        return _result(None, "not_first_half_double_chance", 0.0)

    if "first half" not in market and "1st half" not in market:
        return _result(None, "not_first_half_double_chance", 0.0)

    if selection in ["1x", "1 x", "home draw", "home or draw"]:
        return _result("first_half_double_chance_1x", "first_half_double_chance_1x", 0.96, "FIRST_HALF_DOUBLE_CHANCE", "FIRST_HALF")

    if selection in ["x2", "x 2", "draw away", "draw or away"]:
        return _result("first_half_double_chance_x2", "first_half_double_chance_x2", 0.96, "FIRST_HALF_DOUBLE_CHANCE", "FIRST_HALF")

    if selection in ["12", "1 2", "home away", "home or away"]:
        return _result("first_half_double_chance_12", "first_half_double_chance_12", 0.96, "FIRST_HALF_DOUBLE_CHANCE", "FIRST_HALF")

    return _result(None, "first_half_double_chance_unmatched_selection", 0.0)


def _normalize_btts(market: str, selection: str) -> NormalizedOddsResult:
    if not any(x in market for x in ["both teams score", "both teams to score", "btts", "both team score"]):
        return _result(None, "not_btts", 0.0)

    if selection in ["yes", "y"]:
        return _result("btts_yes", "btts_yes", 0.99, "BTTS", "FULL_TIME")

    if selection in ["no", "n"]:
        return _result("btts_no", "btts_no", 0.99, "BTTS", "FULL_TIME")

    return _result(None, "btts_unmatched_selection", 0.0)


def _normalize_result_total_goals(market: str, selection: str) -> NormalizedOddsResult:
    if "result total goals" not in market and "result total" not in market:
        return _result(None, "not_result_total_goals", 0.0)

    parts = selection.split()
    if len(parts) < 3:
        return _result(None, "result_total_bad_selection", 0.0)

    outcome = parts[0]
    direction = parts[1]
    line = extract_line(selection)

    outcome_map = {"home": "home", "1": "home", "draw": "draw", "x": "draw", "away": "away", "2": "away"}

    if outcome not in outcome_map:
        return _result(None, "result_total_unknown_outcome", 0.0)

    if direction not in ["over", "under"] or line is None:
        return _result(None, "result_total_unknown_direction_or_line", 0.0)

    key = f"result_total_{outcome_map[outcome]}_{direction}_{line_to_key(line)}_goals"

    if is_supported_market(key):
        return _result(key, f"result_total_{outcome}_{direction}_{line}", 0.93, "RESULT_TOTAL_GOALS", "FULL_TIME", None, line)

    return _result(None, "result_total_unsupported_line", 0.0)


def _normalize_handicap_result(market: str, selection: str) -> NormalizedOddsResult:
    if market != "handicap result":
        return _result(None, "not_handicap_result", 0.0)

    outcome = None
    if selection.startswith("home"):
        outcome = "home"
    elif selection.startswith("draw"):
        outcome = "draw"
    elif selection.startswith("away"):
        outcome = "away"

    if not outcome:
        return _result(None, "handicap_result_unknown_outcome", 0.0)

    line = extract_line(selection)
    if line is None:
        return _result(None, "handicap_result_missing_line", 0.0)

    key = f"handicap_result_{outcome}_{signed_line_to_key(line)}"

    if is_supported_market(key):
        return _result(key, f"handicap_result_{outcome}_{line}", 0.93, "HANDICAP_RESULT", "FULL_TIME", outcome.upper(), line)

    return _result(None, "handicap_result_unsupported_line", 0.0)


def _normalize_first_half_exact_score(market: str, selection: str) -> NormalizedOddsResult:
    if "correct score first half" not in market and "correct score 1st half" not in market:
        return _result(None, "not_first_half_exact_score", 0.0)

    match = re.search(r"(\d+)\s*:\s*(\d+)", selection)
    if not match:
        return _result(None, "first_half_exact_score_bad_selection", 0.0)

    home_score = int(match.group(1))
    away_score = int(match.group(2))

    key = (
        f"first_half_exact_score_{home_score}_{away_score}"
        if home_score <= 4 and away_score <= 4
        else "first_half_exact_score_other"
    )

    if is_supported_market(key):
        return _result(key, f"first_half_exact_score_{home_score}_{away_score}", 0.95, "FIRST_HALF_EXACT_SCORE", "FIRST_HALF")

    return _result(None, "first_half_exact_score_unsupported", 0.0)


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
        if "first half" in market or "second half" in market:
            is_scope = False
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
        if is_supported_market(key):
            return _result(key, f"{reason_prefix}_over_{line}", 0.98, "GOALS", scope, None, line)

    if "under" in selection or "under" in combined:
        key = f"{prefix}under_{normalized_line}_goals"
        if is_supported_market(key):
            return _result(key, f"{reason_prefix}_under_{line}", 0.98, "GOALS", scope, None, line)

    return _result(None, "total_goals_unmatched_direction", 0.0)


def _normalize_corners(market: str, selection: str, combined: str) -> NormalizedOddsResult:
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


def _normalize_team_totals(market: str, selection: str, combined: str, home: str, away: str) -> NormalizedOddsResult:
    if not any(x in combined for x in ["team total", "total home", "total away", "home total", "away total", "total home team", "total away team", "home goals", "away goals"]):
        return _result(None, "not_team_total", 0.0)

    line = extract_line(combined)
    if line is None:
        return _result(None, "missing_team_total_line", 0.0)

    normalized_line = line_to_key(line)

    team_scope = None
    if "total home" in market or "home total" in market or "home" in market or (home and home in combined):
        team_scope = "home"
    elif "total away" in market or "away total" in market or "away" in market or (away and away in combined):
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


def _normalize_asian_handicap(market: str, selection: str, combined: str, home: str, away: str) -> NormalizedOddsResult:
    if "asian handicap" not in combined:
        return _result(None, "not_asian_handicap", 0.0)

    team_scope = None
    if "home" in selection or selection == home or (home and home in selection):
        team_scope = "home"
    elif "away" in selection or selection == away or (away and away in selection):
        team_scope = "away"

    if not team_scope:
        return _result(None, "missing_asian_team_scope", 0.0)

    line = extract_line(combined)
    if line is None:
        return _result(None, "missing_asian_line", 0.0)

    if line == 0:
        key = f"asian_handicap_{team_scope}_0_0"
    else:
        key = f"asian_handicap_{team_scope}_{signed_line_to_key(line)}"

    if is_supported_market(key):
        return _result(key, f"asian_handicap_{team_scope}_{line}", 0.96, "ASIAN_HANDICAP", "FULL_TIME", team_scope.upper(), line)

    return _result(None, "asian_handicap_unsupported_line", 0.0)


def detect_market_family(canonical_market: str | None) -> str | None:
    if not canonical_market:
        return None

    market = canonical_market.lower()

    if market in ["home_win", "away_win", "draw"]:
        return "MATCH_RESULT"
    if market.startswith("home_away"):
        return "HOME_AWAY_2WAY"
    if market.startswith("double_chance"):
        return "DOUBLE_CHANCE"
    if market.startswith("first_half_double_chance"):
        return "FIRST_HALF_DOUBLE_CHANCE"
    if market.startswith("btts"):
        return "BTTS"
    if market.startswith("corners"):
        return "CORNERS"
    if market.startswith("asian_handicap"):
        return "ASIAN_HANDICAP"
    if market.startswith("handicap_result"):
        return "HANDICAP_RESULT"
    if market.startswith("result_total"):
        return "RESULT_TOTAL_GOALS"
    if market.startswith("first_half_exact_score"):
        return "FIRST_HALF_EXACT_SCORE"
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