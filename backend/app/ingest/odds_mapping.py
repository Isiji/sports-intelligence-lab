from typing import Any


def normalize_market_selection(
    provider_market: Any,
    provider_selection: Any,
    line_value: float | None = None,
) -> tuple[str, str] | None:
    market = _clean(provider_market)
    selection = _clean(provider_selection)

    if market in {"match winner", "1x2", "fulltime result"}:
        if selection in {"home", "1"}:
            return "home_win", "HOME_WIN"
        if selection in {"away", "2"}:
            return "away_win", "AWAY_WIN"
        if selection in {"draw", "x"}:
            return "draw", "DRAW"

    if market in {"home/away"}:
        if selection in {"home", "1"}:
            return "home_win", "HOME_WIN"
        if selection in {"away", "2"}:
            return "away_win", "AWAY_WIN"

    if market in {"both teams score", "both teams to score", "btts"}:
        if selection == "yes":
            return "btts_yes", "BTTS_YES"
        if selection == "no":
            return "btts_no", "BTTS_NO"

    if market in {"goals over/under", "over/under", "total goals"}:
        if line_value == 2.5:
            if selection in {"over", "over 2.5"}:
                return "over_2_5_goals", "OVER_2_5"
            if selection in {"under", "under 2.5"}:
                return "under_2_5_goals", "UNDER_2_5"

    if market == "double chance":
        if selection in {"home/draw", "1x"}:
            return "double_chance_1x", "DOUBLE_CHANCE_1X"
        if selection in {"draw/away", "x2"}:
            return "double_chance_x2", "DOUBLE_CHANCE_X2"
        if selection in {"home/away", "12"}:
            return "double_chance_12", "DOUBLE_CHANCE_12"

    return None


def extract_line_value(raw_value: Any) -> float | None:
    if raw_value is None:
        return None

    text = str(raw_value).strip()

    for token in text.replace(",", ".").split():
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