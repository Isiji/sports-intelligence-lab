import re
from dataclasses import dataclass

from app.odds.canonical_markets import is_supported_market


@dataclass(frozen=True)
class NormalizedOddsResult:
    canonical_market: str | None
    reason: str
    confidence: float


def clean_text(value: str | None) -> str:
    if not value:
        return ""

    value = value.lower().strip()
    value = value.replace("-", " ")
    value = value.replace("_", " ")
    value = re.sub(r"\s+", " ", value)
    return value


def normalize_direct_market(value: str | None) -> str | None:
    cleaned = clean_text(value)
    key = cleaned.replace(" ", "_")

    if is_supported_market(key):
        return key

    return None


def extract_goal_line(text: str) -> str | None:
    match = re.search(r"(0\.5|1\.5|2\.5|3\.5|4\.5|5\.5)", text)
    return match.group(1) if match else None


def normalize_market_and_selection(
    market_name: str | None,
    selection_name: str | None,
    home_team: str | None = None,
    away_team: str | None = None,
) -> NormalizedOddsResult:
    direct = normalize_direct_market(selection_name) or normalize_direct_market(market_name)
    if direct:
        return NormalizedOddsResult(direct, "already_canonical", 1.0)

    market = clean_text(market_name)
    selection = clean_text(selection_name)
    home = clean_text(home_team)
    away = clean_text(away_team)

    combined = f"{market} {selection}".strip()

    # Match winner / 1X2
    if any(x in market for x in ["match winner", "winner", "1x2", "fulltime result", "full time result"]):
        if selection in ["home", "1", "team 1"] or selection == home:
            return NormalizedOddsResult("home_win", "match_winner_home", 0.98)
        if selection in ["draw", "x"] or "draw" in selection:
            return NormalizedOddsResult("draw", "match_winner_draw", 0.98)
        if selection in ["away", "2", "team 2"] or selection == away:
            return NormalizedOddsResult("away_win", "match_winner_away", 0.98)

    # Double chance
    if "double chance" in market or market in ["dc"]:
        if selection in ["1x", "home/draw", "home or draw", "1/x"]:
            return NormalizedOddsResult("double_chance_1x", "double_chance_1x", 0.98)
        if selection in ["x2", "draw/away", "draw or away", "x/2"]:
            return NormalizedOddsResult("double_chance_x2", "double_chance_x2", 0.98)
        if selection in ["12", "1 2", "home/away", "home or away", "1/2"]:
            return NormalizedOddsResult("double_chance_12", "double_chance_12", 0.98)

    # BTTS
    if (
        "both teams score" in market
        or "both teams to score" in market
        or "btts" in market
        or "both team score" in market
    ):
        if selection in ["yes", "y"]:
            return NormalizedOddsResult("btts_yes", "btts_yes", 0.99)
        if selection in ["no", "n"]:
            return NormalizedOddsResult("btts_no", "btts_no", 0.99)

    # Goals over/under
    if any(x in market for x in ["goals over under", "over under", "total goals", "goals total"]):
        line = extract_goal_line(combined)

        if line:
            normalized_line = line.replace(".", "_")

            if "over" in selection or "over" in combined:
                key = f"over_{normalized_line}_goals"
                if is_supported_market(key):
                    return NormalizedOddsResult(key, f"goals_over_{line}", 0.98)

            if "under" in selection or "under" in combined:
                key = f"under_{normalized_line}_goals"
                if is_supported_market(key):
                    return NormalizedOddsResult(key, f"goals_under_{line}", 0.98)

    return NormalizedOddsResult(None, "unsupported_or_unmatched_market", 0.0)