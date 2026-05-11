from typing import Any


def normalize_market_selection(
    provider_market: Any,
    provider_selection: Any,
    line_value: float | None = None,
) -> tuple[str, str] | None:
    market = _clean(provider_market)
    selection = _clean(provider_selection)

    # 1X2 / Match Winner
    if market in {
        "match winner",
        "1x2",
        "fulltime result",
        "full time result",
        "full-time result",
        "winner",
        "match result",
    }:
        return _map_1x2(selection)

    # Draw No Bet
    if market in {
        "draw no bet",
        "dnb",
        "match winner draw no bet",
    }:
        if selection in {"home", "1"}:
            return "draw_no_bet_home", "DRAW_NO_BET_HOME"
        if selection in {"away", "2"}:
            return "draw_no_bet_away", "DRAW_NO_BET_AWAY"

    # First Half Winner
    if market in {
        "first half winner",
        "1st half winner",
        "first half result",
        "1st half result",
        "half time result",
        "halftime result",
    }:
        mapped = _map_1x2(selection)
        if mapped:
            internal_market, internal_selection = mapped
            return f"first_half_{internal_market}", f"FIRST_HALF_{internal_selection}"

    # Second Half Winner
    if market in {
        "second half winner",
        "2nd half winner",
        "second half result",
        "2nd half result",
    }:
        mapped = _map_1x2(selection)
        if mapped:
            internal_market, internal_selection = mapped
            return f"second_half_{internal_market}", f"SECOND_HALF_{internal_selection}"

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

    # First Half BTTS
    if market in {
        "both teams to score first half",
        "1st half both teams to score",
        "first half both teams score",
        "1st half btts",
    }:
        if selection == "yes":
            return "first_half_btts_yes", "FIRST_HALF_BTTS_YES"
        if selection == "no":
            return "first_half_btts_no", "FIRST_HALF_BTTS_NO"

    # Full Match Goals
    if market in {
        "goals over/under",
        "over/under",
        "total goals",
        "match goals",
        "total goals over/under",
    }:
        return _map_goal_line(line_value, selection, "")

    # First Half Goals
    if market in {
        "goals over/under first half",
        "1st half goals over/under",
        "1st half over/under",
        "first half goals over/under",
        "first half over/under",
        "1st half total goals",
        "first half total goals",
    }:
        return _map_goal_line(line_value, selection, "first_half_")

    # Second Half Goals
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
        return _map_goal_line(line_value, selection, "second_half_")

    # Home Team Total Goals
    if market in {
        "home team total goals",
        "home total goals",
        "home goals over/under",
        "home team goals over/under",
        "home team over/under",
        "home team total",
        "home goals",
    }:
        return _map_team_goal_line("home", line_value, selection)

    # Away Team Total Goals
    if market in {
        "away team total goals",
        "away total goals",
        "away goals over/under",
        "away team goals over/under",
        "away team over/under",
        "away team total",
        "away goals",
    }:
        return _map_team_goal_line("away", line_value, selection)

    # Double Chance
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
        return _map_asian_handicap(selection, line_value)

    # Corners
    if market in {
        "corners over under",
        "corners over/under",
        "total corners",
        "corner over/under",
        "total corners over/under",
    }:
        return _map_corner_line(line_value, selection)

    # HT/FT
    if market in {
        "ht/ft double",
        "ht ft double",
        "half time/full time",
        "halftime/fulltime",
        "half-time/full-time",
        "ht/ft",
    }:
        return _map_ht_ft(selection)

    # Highest Scoring Half
    if market in {
        "highest scoring half",
        "which half will have most goals",
        "most goals half",
    }:
        if selection in {"1st half", "first half", "1"}:
            return "highest_scoring_half_first", "HIGHEST_SCORING_HALF_FIRST"
        if selection in {"2nd half", "second half", "2"}:
            return "highest_scoring_half_second", "HIGHEST_SCORING_HALF_SECOND"
        if selection in {"equal", "tie", "draw"}:
            return "highest_scoring_half_equal", "HIGHEST_SCORING_HALF_EQUAL"

    # Win To Nil
    if market in {
        "win to nil",
        "team to win to nil",
    }:
        if selection in {"home", "home yes", "1"}:
            return "home_win_to_nil", "HOME_WIN_TO_NIL"
        if selection in {"away", "away yes", "2"}:
            return "away_win_to_nil", "AWAY_WIN_TO_NIL"

    # Exact Score
    if market in {
        "exact score",
        "correct score",
        "fulltime correct score",
        "full time correct score",
    }:
        return _map_exact_score(selection)

    return None


def _map_1x2(selection: str) -> tuple[str, str] | None:
    if selection in {"home", "1"}:
        return "home_win", "HOME_WIN"
    if selection in {"away", "2"}:
        return "away_win", "AWAY_WIN"
    if selection in {"draw", "x"}:
        return "draw", "DRAW"
    return None


def _map_goal_line(
    line_value: float | None,
    selection: str,
    market_prefix: str,
) -> tuple[str, str] | None:
    selection = _clean(selection)

    for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
        if line_value == line:
            key = _line_key(line)
            prefix_upper = market_prefix.upper()

            if selection in {"over", f"over {line}"}:
                return f"{market_prefix}over_{key}_goals", f"{prefix_upper}OVER_{key.upper()}"

            if selection in {"under", f"under {line}"}:
                return f"{market_prefix}under_{key}_goals", f"{prefix_upper}UNDER_{key.upper()}"

    return None


def _map_team_goal_line(
    side: str,
    line_value: float | None,
    selection: str,
) -> tuple[str, str] | None:
    selection = _clean(selection)

    for line in [0.5, 1.5, 2.5, 3.5]:
        if line_value == line:
            key = _line_key(line)
            upper = side.upper()

            if selection in {"over", f"over {line}", f"{side} over {line}"}:
                return f"{side}_over_{key}_goals", f"{upper}_OVER_{key.upper()}"

            if selection in {"under", f"under {line}", f"{side} under {line}"}:
                return f"{side}_under_{key}_goals", f"{upper}_UNDER_{key.upper()}"

    return None


def _map_corner_line(
    line_value: float | None,
    selection: str,
) -> tuple[str, str] | None:
    selection = _clean(selection)

    for line in [7.5, 8.5, 9.5, 10.5, 11.5]:
        if line_value == line:
            key = _line_key(line)

            if selection in {"over", f"over {line}"}:
                return f"corners_over_{key}", f"CORNERS_OVER_{key.upper()}"

            if selection in {"under", f"under {line}"}:
                return f"corners_under_{key}", f"CORNERS_UNDER_{key.upper()}"

    return None


def _map_asian_handicap(
    selection: str,
    line_value: float | None,
) -> tuple[str, str] | None:
    selection = _clean(selection)

    if line_value is None:
        return None

    if selection.startswith(("home", "1")):
        side = "home"
    elif selection.startswith(("away", "2")):
        side = "away"
    else:
        return None

    key = _handicap_key(line_value)

    return (
        f"asian_handicap_{side}_{key}",
        f"ASIAN_HANDICAP_{side.upper()}_{key.upper()}",
    )


def _map_ht_ft(selection: str) -> tuple[str, str] | None:
    selection = _clean(selection)

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

    return mapping.get(selection)


def _map_exact_score(selection: str) -> tuple[str, str] | None:
    selection = _clean(selection).replace("-", ":")

    if ":" not in selection:
        return None

    parts = selection.split(":")

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

    for word in [
        "over",
        "under",
        "home",
        "away",
        "draw",
        "yes",
        "no",
    ]:
        text = text.replace(word, " ")

    for token in text.replace("(", " ").replace(")", " ").split():
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