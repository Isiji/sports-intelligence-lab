# backend/app/odds/production_label_resolver.py

from __future__ import annotations


LABEL_TO_MARKET = {
    "HOME_WIN": "home_win",
    "AWAY_WIN": "away_win",
    "DRAW": "draw",

    "NOT_HOME_WIN": "double_chance_x2",
    "NOT_AWAY_WIN": "double_chance_1x",
    "NOT_DRAW": "double_chance_12",

    "DOUBLE_CHANCE_1X": "double_chance_1x",
    "DOUBLE_CHANCE_X2": "double_chance_x2",
    "DOUBLE_CHANCE_12": "double_chance_12",

    "NOT_DOUBLE_CHANCE_1X": "away_win",
    "NOT_DOUBLE_CHANCE_X2": "home_win",
    "NOT_DOUBLE_CHANCE_12": "draw",

    "OVER_1_5": "over_1_5_goals",
    "UNDER_1_5": "under_1_5_goals",
    "OVER_2_5": "over_2_5_goals",
    "UNDER_2_5": "under_2_5_goals",
    "OVER_3_5": "over_3_5_goals",
    "UNDER_3_5": "under_3_5_goals",

    "BTTS_YES": "btts_yes",
    "BTTS_NO": "btts_no",

    "HOME_OVER_0_5": "home_over_0_5_goals",
    "AWAY_OVER_0_5": "away_over_0_5_goals",
    "HOME_CLEAN_SHEET": "home_clean_sheet",
    "AWAY_CLEAN_SHEET": "away_clean_sheet",
}


def resolve_executable_market(
    *,
    target_market: str,
    predicted_label: str | None,
) -> str:
    if not predicted_label:
        return target_market

    label = predicted_label.upper().strip()

    if label in LABEL_TO_MARKET:
        return LABEL_TO_MARKET[label]

    if label.startswith("ASIAN_HANDICAP_"):
        return label.lower()

    if label.startswith("NOT_ASIAN_HANDICAP_"):
        return _invert_asian_handicap(label)

    return target_market


def _invert_asian_handicap(label: str) -> str:
    raw = label.replace("NOT_ASIAN_HANDICAP_", "ASIAN_HANDICAP_").lower()

    if "_home_" in raw:
        raw = raw.replace("_home_", "_away_")
    elif "_away_" in raw:
        raw = raw.replace("_away_", "_home_")

    if "_plus_" in raw:
        raw = raw.replace("_plus_", "_minus_")
    elif "_minus_" in raw:
        raw = raw.replace("_minus_", "_plus_")

    return raw