# backend/app/odds/production_label_resolver.py

from __future__ import annotations

from app.odds.execution_market_mapping import (
    build_asian_handicap_family_candidates,
    market_execution_family,
)


LABEL_TO_MARKET: dict[str, str] = {
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

    "OVER_0_5": "over_0_5_goals",
    "UNDER_0_5": "under_0_5_goals",
    "OVER_1_5": "over_1_5_goals",
    "UNDER_1_5": "under_1_5_goals",
    "OVER_2_5": "over_2_5_goals",
    "UNDER_2_5": "under_2_5_goals",
    "OVER_3_5": "over_3_5_goals",
    "UNDER_3_5": "under_3_5_goals",
    "OVER_4_5": "over_4_5_goals",
    "UNDER_4_5": "under_4_5_goals",

    "BTTS_YES": "btts_yes",
    "BTTS_NO": "btts_no",

    "HOME_OVER_0_5": "home_over_0_5_goals",
    "HOME_UNDER_0_5": "home_under_0_5_goals",
    "HOME_OVER_1_5": "home_over_1_5_goals",
    "HOME_UNDER_1_5": "home_under_1_5_goals",

    "AWAY_OVER_0_5": "away_over_0_5_goals",
    "AWAY_UNDER_0_5": "away_under_0_5_goals",
    "AWAY_OVER_1_5": "away_over_1_5_goals",
    "AWAY_UNDER_1_5": "away_under_1_5_goals",

    "HOME_CLEAN_SHEET": "home_clean_sheet",
    "AWAY_CLEAN_SHEET": "away_clean_sheet",

    "CORNERS_OVER_8_5": "corners_over_8_5",
    "CORNERS_UNDER_8_5": "corners_under_8_5",

    "SOT_OVER_8_5": "shots_on_target_over_8_5",
    "SOT_UNDER_8_5": "shots_on_target_under_8_5",
    "SHOTS_ON_TARGET_OVER_8_5": "shots_on_target_over_8_5",
    "SHOTS_ON_TARGET_UNDER_8_5": "shots_on_target_under_8_5",

    "DRAW_NO_BET_HOME": "draw_no_bet_home",
    "DRAW_NO_BET_AWAY": "draw_no_bet_away",
    "NOT_DRAW_NO_BET_HOME": "draw_no_bet_away",
    "NOT_DRAW_NO_BET_AWAY": "draw_no_bet_home",

    "HOME_AWAY_HOME": "home_away_home",
    "HOME_AWAY_AWAY": "home_away_away",

    "FIRST_HALF_DOUBLE_CHANCE_1X": "first_half_double_chance_1x",
    "FIRST_HALF_DOUBLE_CHANCE_X2": "first_half_double_chance_x2",
    "FIRST_HALF_DOUBLE_CHANCE_12": "first_half_double_chance_12",
}


INVERSE_MARKET_MAP: dict[str, str] = {
    "over_0_5_goals": "under_0_5_goals",
    "under_0_5_goals": "over_0_5_goals",
    "over_1_5_goals": "under_1_5_goals",
    "under_1_5_goals": "over_1_5_goals",
    "over_2_5_goals": "under_2_5_goals",
    "under_2_5_goals": "over_2_5_goals",
    "over_3_5_goals": "under_3_5_goals",
    "under_3_5_goals": "over_3_5_goals",

    "btts_yes": "btts_no",
    "btts_no": "btts_yes",

    "home_over_0_5_goals": "home_under_0_5_goals",
    "home_under_0_5_goals": "home_over_0_5_goals",
    "away_over_0_5_goals": "away_under_0_5_goals",
    "away_under_0_5_goals": "away_over_0_5_goals",

    "corners_over_8_5": "corners_under_8_5",
    "corners_under_8_5": "corners_over_8_5",

    "shots_on_target_over_8_5": "shots_on_target_under_8_5",
    "shots_on_target_under_8_5": "shots_on_target_over_8_5",

    "draw_no_bet_home": "draw_no_bet_away",
    "draw_no_bet_away": "draw_no_bet_home",
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

    if label.startswith("NOT_ASIAN_HANDICAP_"):
        return _invert_asian_handicap(label)

    if label.startswith("ASIAN_HANDICAP_"):
        return label.lower()

    if label.startswith("NOT_"):
        positive_label = label.replace("NOT_", "", 1)
        positive_market = LABEL_TO_MARKET.get(positive_label)

        if positive_market:
            return INVERSE_MARKET_MAP.get(positive_market, target_market)

    return target_market


def resolve_execution_family(
    *,
    target_market: str,
    predicted_label: str | None,
) -> str:
    executable_market = resolve_executable_market(
        target_market=target_market,
        predicted_label=predicted_label,
    )

    return market_execution_family(executable_market)


def resolve_execution_market_candidates(
    *,
    target_market: str,
    predicted_label: str | None,
) -> list[str]:
    executable_market = resolve_executable_market(
        target_market=target_market,
        predicted_label=predicted_label,
    )

    if executable_market.startswith("asian_handicap_"):
        return build_asian_handicap_family_candidates(
            source_market=executable_market,
        )

    return [executable_market]


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