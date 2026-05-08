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

    # Second half winner
    if market in {
        "second half winner",
        "2nd half winner",
        "second half result",
        "2nd half result",
    }:
        if selection in {"home", "1"}:
            return "second_half_home_win", "SECOND_HALF_HOME_WIN"
        if selection in {"away", "2"}:
            return "second_half_away_win", "SECOND_HALF_AWAY_WIN"
        if selection in {"draw", "x"}:
            return "second_half_draw", "SECOND_HALF_DRAW"

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

    # First half goals over/under
    if market in {
        "goals over/under first half",
        "1st half goals over/under",
        "1st half over/under",
        "first half goals over/under",
        "first half over/under",
        "1st half total goals",
        "first half total goals",
    }:
        return _map_goal_line(
            line_value=line_value,
            selection=selection,
            market_prefix="first_half_",
        )

    # Second half goals over/under
    if market in {
        "goals over/under - second half",
        "goals over/under second half",
        "2nd half goals over/under",
        "2nd half over/under",
        "second half goals over/under",
        "second half over/under",
        "2nd half total goals",
        "second half total goals",
    }:
        return _map_goal_line(
            line_value=line_value,
            selection=selection,
            market_prefix="second_half_",
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
        return _map_team_goal_line(
            side="home",
            line_value=line_value,
            selection=selection,
        )

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
        return _map_team_goal_line(
            side="away",
            line_value=line_value,
            selection=selection,
        )

    # Corners over/under
    if market in {
        "corners over under",
        "corners over/under",
        "total corners",
        "corners",
        "corner over/under",
        "total corners over/under",
    }:
        return _map_corner_line(
            line_value=line_value,
            selection=selection,
        )

    # Double chance
    if market == "double chance":
        if selection in {"home/draw", "1x", "home or draw"}:
            return "double_chance_1x", "DOUBLE_CHANCE_1X"
        if selection in {"draw/away", "x2", "draw or away"}:
            return "double_chance_x2", "DOUBLE_CHANCE_X2"
        if selection in {"home/away", "12", "home or away"}:
            return "double_chance_12", "DOUBLE_CHANCE_12"

    # Asian Handicap
    if market in {
        "asian handicap",
        "handicap",
        "asian handicap full time",
        "asian handicap fulltime",
    }:
        return _map_asian_handicap(selection=selection, line_value=line_value)

    # HT/FT Double
    if market in {
        "ht/ft double",
        "ht ft double",
        "half time/full time",
        "halftime/fulltime",
        "half-time/full-time",
        "ht/ft",
    }:
        return _map_ht_ft(selection=selection)

    # Exact Score
    if market in {
        "exact score",
        "correct score",
        "fulltime correct score",
        "full time correct score",
    }:
        return _map_exact_score(selection=selection)

    return None


def _map_goal_line(
    line_value: float | None,
    selection: str,
    market_prefix: str = "",
) -> tuple[str, str] | None:
    normalized_selection = _clean(selection)

    supported_lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]

    for line in supported_lines:
        if line_value == line:
            line_key = _line_key(line)

            if normalized_selection in {"over", f"over {line}"}:
                return (
                    f"{market_prefix}over_{line_key}_goals",
                    f"{market_prefix.upper()}OVER_{line_key.upper()}",
                )

            if normalized_selection in {"under", f"under {line}"}:
                return (
                    f"{market_prefix}under_{line_key}_goals",
                    f"{market_prefix.upper()}UNDER_{line_key.upper()}",
                )

    return None


def _map_team_goal_line(
    side: str,
    line_value: float | None,
    selection: str,
) -> tuple[str, str] | None:
    normalized_selection = _clean(selection)

    supported_lines = [0.5, 1.5, 2.5, 3.5]

    for line in supported_lines:
        if line_value == line:
            line_key = _line_key(line)
            side_upper = side.upper()

            if normalized_selection in {
                "over",
                f"over {line}",
                f"{side} over {line}",
            }:
                return (
                    f"{side}_over_{line_key}_goals",
                    f"{side_upper}_OVER_{line_key.upper()}",
                )

            if normalized_selection in {
                "under",
                f"under {line}",
                f"{side} under {line}",
            }:
                return (
                    f"{side}_over_{line_key}_goals",
                    f"{side_upper}_UNDER_{line_key.upper()}",
                )

    return None


def _map_corner_line(
    line_value: float | None,
    selection: str,
) -> tuple[str, str] | None:
    normalized_selection = _clean(selection)

    supported_lines = [7.5, 8.5, 9.5, 10.5, 11.5]

    for line in supported_lines:
        if line_value == line:
            line_key = _line_key(line)

            if normalized_selection in {"over", f"over {line}"}:
                return (
                    f"corners_over_{line_key}",
                    f"CORNERS_OVER_{line_key.upper()}",
                )

            if normalized_selection in {"under", f"under {line}"}:
                return (
                    f"corners_over_{line_key}",
                    f"CORNERS_UNDER_{line_key.upper()}",
                )

    return None


def _map_asian_handicap(
    selection: str,
    line_value: float | None,
) -> tuple[str, str] | None:
    normalized_selection = _clean(selection)

    if line_value is None:
        return None

    side = None

    if normalized_selection.startswith("home"):
        side = "home"
    elif normalized_selection.startswith("away"):
        side = "away"

    if side is None:
        return None

    handicap_key = _handicap_key(line_value)
    side_upper = side.upper()

    return (
        f"asian_handicap_{side}_{handicap_key}",
        f"ASIAN_HANDICAP_{side_upper}_{handicap_key.upper()}",
    )


def _map_ht_ft(selection: str) -> tuple[str, str] | None:
    normalized_selection = _clean(selection)

    mapping = {
        "home/home": ("ht_ft_home_home", "HT_FT_HOME_HOME"),
        "home/draw": ("ht_ft_home_draw", "HT_FT_HOME_DRAW"),
        "home/away": ("ht_ft_home_away", "HT_FT_HOME_AWAY"),
        "draw/home": ("ht_ft_draw_home", "HT_FT_DRAW_HOME"),
        "draw/draw": ("ht_ft_draw_draw", "HT_FT_DRAW_DRAW"),
        "draw/away": ("ht_ft_draw_away", "HT_FT_DRAW_AWAY"),
        "away/home": ("ht_ft_away_home", "HT_FT_AWAY_HOME"),
        "away/draw": ("ht_ft_away_draw", "HT_FT_AWAY_DRAW"),
        "away/away": ("ht_ft_away_away", "HT_FT_AWAY_AWAY"),
    }

    return mapping.get(normalized_selection)


def _map_exact_score(selection: str) -> tuple[str, str] | None:
    normalized_selection = _clean(selection)

    if ":" not in normalized_selection:
        return None

    parts = normalized_selection.split(":")

    if len(parts) != 2:
        return None

    try:
        home_goals = int(parts[0])
        away_goals = int(parts[1])
    except ValueError:
        return None

    if home_goals < 0 or away_goals < 0:
        return None

    if home_goals > 9 or away_goals > 9:
        return None

    return (
        f"exact_score_{home_goals}_{away_goals}",
        f"EXACT_SCORE_{home_goals}_{away_goals}",
    )


def extract_line_value(raw_value: Any) -> float | None:
    if raw_value is None:
        return None

    text = str(raw_value).strip().lower()
    text = text.replace(",", ".")

    for word in ["over", "under", "home", "away"]:
        text = text.replace(word, " ")

    # Keep + and - because Asian Handicap needs negative and positive lines.
    for token in text.split():
        try:
            return float(token)
        except ValueError:
            continue

    try:
        return float(text)
    except ValueError:
        return None


def _line_key(line_value: float) -> str:
    return str(line_value).replace(".", "_").replace("-", "minus_")


def _handicap_key(line_value: float) -> str:
    if line_value < 0:
        return "minus_" + str(abs(line_value)).replace(".", "_")

    if line_value > 0:
        return "plus_" + str(line_value).replace(".", "_")

    return "zero"


def _clean(value: Any) -> str:
    return " ".join(str(value).lower().strip().split())