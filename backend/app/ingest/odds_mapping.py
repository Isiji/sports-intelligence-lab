# backend/app/ingest/odds_mapping.py

from typing import Any


def normalize_market_selection(
    provider_market: Any,
    provider_selection: Any,
    line_value: float | None = None,
) -> tuple[str, str] | None:
    market = _clean(provider_market)
    selection = _clean(provider_selection)

    # 1X2 / Match winner
    if market in {
        "match winner",
        "1x2",
        "fulltime result",
        "full time result",
        "full-time result",
        "winner",
        "match result",
    }:
        if selection in {"home", "1"}:
            return "home_win", "HOME_WIN"
        if selection in {"away", "2"}:
            return "away_win", "AWAY_WIN"
        if selection in {"draw", "x"}:
            return "draw", "DRAW"

    # Home/Away without draw
    if market in {"home/away", "home away"}:
        if selection in {"home", "1"}:
            return "home_win", "HOME_WIN"
        if selection in {"away", "2"}:
            return "away_win", "AWAY_WIN"

    # BTTS
    if market in {
        "both teams score",
        "both teams to score",
        "both teams to score - yes/no",
        "btts",
    }:
        if selection == "yes":
            return "btts_yes", "BTTS_YES"
        if selection == "no":
            return "btts_no", "BTTS_NO"

    # Goals Over/Under
    if market in {
        "goals over/under",
        "over/under",
        "total goals",
        "match goals",
        "total goals over/under",
    }:
        return _map_goal_line(
            line_value=line_value,
            selection=selection,
            market_prefix="",
        )

    # Home team total goals
    if market in {
        "home team total goals",
        "home total goals",
        "home goals over/under",
        "home team goals over/under",
        "home team over/under",
        "team goals home",
        "home team goals",
        "home goals",
        "home over/under",
        "home team total",
    }:
        if line_value == 0.5:
            if selection in {"over", "over 0.5", "home over 0.5"}:
                return "home_over_0_5_goals", "HOME_OVER_0_5"
            if selection in {"under", "under 0.5", "home under 0.5"}:
                return "home_over_0_5_goals", "HOME_UNDER_0_5"

    # Away team total goals
    if market in {
        "away team total goals",
        "away total goals",
        "away goals over/under",
        "away team goals over/under",
        "away team over/under",
        "team goals away",
        "away team goals",
        "away goals",
        "away over/under",
        "away team total",
    }:
        if line_value == 0.5:
            if selection in {"over", "over 0.5", "away over 0.5"}:
                return "away_over_0_5_goals", "AWAY_OVER_0_5"
            if selection in {"under", "under 0.5", "away under 0.5"}:
                return "away_over_0_5_goals", "AWAY_UNDER_0_5"

    # Corners over/under
    if market in {
        "corners over under",
        "corners over/under",
        "total corners",
        "corners",
        "corner over/under",
        "total corners over/under",
    }:
        if line_value == 8.5:
            if selection in {"over", "over 8.5"}:
                return "corners_over_8_5", "CORNERS_OVER_8_5"
            if selection in {"under", "under 8.5"}:
                return "corners_over_8_5", "CORNERS_UNDER_8_5"

    # Double chance
    if market == "double chance":
        if selection in {"home/draw", "1x", "home or draw"}:
            return "double_chance_1x", "DOUBLE_CHANCE_1X"
        if selection in {"draw/away", "x2", "draw or away"}:
            return "double_chance_x2", "DOUBLE_CHANCE_X2"
        if selection in {"home/away", "12", "home or away"}:
            return "double_chance_12", "DOUBLE_CHANCE_12"

    return None


def _map_goal_line(
    line_value: float | None,
    selection: str,
    market_prefix: str = "",
) -> tuple[str, str] | None:
    if line_value == 0.5:
        if selection in {"over", "over 0.5"}:
            return "over_0_5_goals", "OVER_0_5"
        if selection in {"under", "under 0.5"}:
            return "under_0_5_goals", "UNDER_0_5"

    if line_value == 1.5:
        if selection in {"over", "over 1.5"}:
            return "over_1_5_goals", "OVER_1_5"
        if selection in {"under", "under 1.5"}:
            return "under_1_5_goals", "UNDER_1_5"

    if line_value == 2.5:
        if selection in {"over", "over 2.5"}:
            return "over_2_5_goals", "OVER_2_5"
        if selection in {"under", "under 2.5"}:
            return "under_2_5_goals", "UNDER_2_5"

    if line_value == 3.5:
        if selection in {"over", "over 3.5"}:
            return "over_3_5_goals", "OVER_3_5"
        if selection in {"under", "under 3.5"}:
            return "under_3_5_goals", "UNDER_3_5"

    return None


def extract_line_value(raw_value: Any) -> float | None:
    if raw_value is None:
        return None

    text = str(raw_value).strip().lower()
    text = text.replace(",", ".")

    for word in ["over", "under", "+"]:
        text = text.replace(word, " ")

    for token in text.split():
        try:
            return float(token)
        except ValueError:
            continue

    try:
        return float(text)
    except ValueError:
        return None


def _clean(value: Any) -> str:
    return " ".join(str(value).lower().strip().split())