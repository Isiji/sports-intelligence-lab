# backend/app/features/rolling_feature_engine.py

from collections import defaultdict, deque

import pandas as pd


INITIAL_ELO = 1500.0
K_FACTOR = 32.0
HOME_ADVANTAGE_ELO = 60.0


def build_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.sort_values(["kickoff_date", "match_id"]).reset_index(drop=True)

    team_history = defaultdict(lambda: deque(maxlen=8))
    home_history = defaultdict(lambda: deque(maxlen=8))
    away_history = defaultdict(lambda: deque(maxlen=8))
    league_history = defaultdict(lambda: deque(maxlen=200))
    h2h_history = defaultdict(lambda: deque(maxlen=6))

    elo = defaultdict(lambda: INITIAL_ELO)
    attack_elo = defaultdict(lambda: INITIAL_ELO)
    defense_elo = defaultdict(lambda: INITIAL_ELO)
    elo_history = defaultdict(lambda: deque(maxlen=5))

    feature_rows = []

    for _, row in df.iterrows():
        home = row["home_team"]
        away = row["away_team"]
        league = row["league"]

        home_hist = list(team_history[home])
        away_hist = list(team_history[away])
        home_home_hist = list(home_history[home])
        away_away_hist = list(away_history[away])
        league_hist = list(league_history[league])

        h2h_key = tuple(sorted([home, away]))
        h2h_hist = list(h2h_history[h2h_key])

        home_elo = elo[home]
        away_elo = elo[away]

        home_attack = attack_elo[home]
        away_attack = attack_elo[away]

        home_defense = defense_elo[home]
        away_defense = defense_elo[away]

        home_elo_form = _elo_form(list(elo_history[home]), home_elo)
        away_elo_form = _elo_form(list(elo_history[away]), away_elo)

        features = {
            "home_elo": home_elo,
            "away_elo": away_elo,
            "elo_diff": (home_elo + HOME_ADVANTAGE_ELO) - away_elo,
            "home_elo_form": home_elo_form,
            "away_elo_form": away_elo_form,
            "elo_form_diff": home_elo_form - away_elo_form,

            "home_attack_elo": home_attack,
            "away_attack_elo": away_attack,
            "home_defense_elo": home_defense,
            "away_defense_elo": away_defense,
            "attack_defense_diff": home_attack - away_defense,

            "home_win_rate": _win_rate(home_hist, home),
            "away_win_rate": _win_rate(away_hist, away),
            "home_goal_diff": _goal_diff(home_hist, home),
            "away_goal_diff": _goal_diff(away_hist, away),
            "home_form_score": _form_score(home_hist, home),
            "away_form_score": _form_score(away_hist, away),

            "home_home_win_rate": _home_win_rate(home_home_hist, home),
            "away_away_win_rate": _away_win_rate(away_away_hist, away),
            "home_current_streak": _current_streak(home_hist, home),
            "away_current_streak": _current_streak(away_hist, away),

            "team_strength_diff": _team_strength(home_hist, home) - _team_strength(away_hist, away),
        }

        features.update(_prefix("home_", _team_profile(home_hist, home)))
        features.update(_prefix("away_", _team_profile(away_hist, away)))
        features.update(_h2h_features(h2h_hist, home, away))
        features.update(_league_profile(league_hist))

        feature_rows.append(features)

        if pd.notna(row["home_goals"]) and pd.notna(row["away_goals"]):
            match_record = _make_match_record(row)

            team_history[home].append(match_record)
            team_history[away].append(match_record)

            home_history[home].append(match_record)
            away_history[away].append(match_record)

            league_history[league].append(match_record)
            h2h_history[h2h_key].append(match_record)

            new_home_elo, new_away_elo = _update_result_elo(
                home_elo=home_elo,
                away_elo=away_elo,
                home_goals=float(row["home_goals"]),
                away_goals=float(row["away_goals"]),
            )

            new_home_attack, new_away_defense = _update_attack_defense_elo(
                attack_rating=home_attack,
                defense_rating=away_defense,
                goals_scored=float(row["home_goals"]),
            )

            new_away_attack, new_home_defense = _update_attack_defense_elo(
                attack_rating=away_attack,
                defense_rating=home_defense,
                goals_scored=float(row["away_goals"]),
            )

            elo_history[home].append(home_elo)
            elo_history[away].append(away_elo)

            elo[home] = new_home_elo
            elo[away] = new_away_elo

            attack_elo[home] = new_home_attack
            defense_elo[away] = new_away_defense

            attack_elo[away] = new_away_attack
            defense_elo[home] = new_home_defense

    features_df = pd.DataFrame(feature_rows)

    return pd.concat(
        [
            df.reset_index(drop=True),
            features_df.reset_index(drop=True),
        ],
        axis=1,
    ).fillna(0.0)


def _make_match_record(row) -> dict:
    return {
        "home_team": row["home_team"],
        "away_team": row["away_team"],
        "home_goals": float(row["home_goals"] or 0),
        "away_goals": float(row["away_goals"] or 0),
        "home_corners": float(row.get("home_corners", 0) or 0),
        "away_corners": float(row.get("away_corners", 0) or 0),
        "home_sot": float(row.get("home_sot", 0) or 0),
        "away_sot": float(row.get("away_sot", 0) or 0),
    }


def _prefix(prefix: str, values: dict[str, float]) -> dict[str, float]:
    return {f"{prefix}{key}": value for key, value in values.items()}


def _elo_form(history: list[float], current_elo: float) -> float:
    if not history:
        return 0.0

    return current_elo - (sum(history) / len(history))


def _update_result_elo(home_elo, away_elo, home_goals, away_goals):
    adjusted_home = home_elo + HOME_ADVANTAGE_ELO

    expected_home = 1 / (1 + 10 ** ((away_elo - adjusted_home) / 400))
    expected_away = 1 - expected_home

    if home_goals > away_goals:
        actual_home = 1.0
    elif home_goals < away_goals:
        actual_home = 0.0
    else:
        actual_home = 0.5

    actual_away = 1 - actual_home

    goal_margin = abs(home_goals - away_goals)
    margin_multiplier = 1 + min(goal_margin, 4) * 0.12

    new_home = home_elo + K_FACTOR * margin_multiplier * (actual_home - expected_home)
    new_away = away_elo + K_FACTOR * margin_multiplier * (actual_away - expected_away)

    return new_home, new_away


def _update_attack_defense_elo(attack_rating, defense_rating, goals_scored):
    expected_goals = 1.35
    performance = goals_scored - expected_goals
    movement = max(min(performance * 10, 24), -24)

    return attack_rating + movement, defense_rating - movement


def _result_for_team(match: dict, team: str) -> str:
    if match["home_team"] == team:
        if match["home_goals"] > match["away_goals"]:
            return "W"
        if match["home_goals"] < match["away_goals"]:
            return "L"
        return "D"

    if match["away_team"] == team:
        if match["away_goals"] > match["home_goals"]:
            return "W"
        if match["away_goals"] < match["home_goals"]:
            return "L"
        return "D"

    return "D"


def _goals_for_against(match: dict, team: str) -> tuple[float, float]:
    if match["home_team"] == team:
        return match["home_goals"], match["away_goals"]

    return match["away_goals"], match["home_goals"]


def _win_rate(matches: list[dict], team: str) -> float:
    if not matches:
        return 0.0

    wins = sum(1 for match in matches if _result_for_team(match, team) == "W")
    return wins / len(matches)


def _home_win_rate(matches: list[dict], team: str) -> float:
    if not matches:
        return 0.0

    wins = sum(
        1
        for match in matches
        if match["home_team"] == team and match["home_goals"] > match["away_goals"]
    )

    return wins / len(matches)


def _away_win_rate(matches: list[dict], team: str) -> float:
    if not matches:
        return 0.0

    wins = sum(
        1
        for match in matches
        if match["away_team"] == team and match["away_goals"] > match["home_goals"]
    )

    return wins / len(matches)


def _goal_diff(matches: list[dict], team: str) -> float:
    if not matches:
        return 0.0

    total = 0.0

    for match in matches:
        gf, ga = _goals_for_against(match, team)
        total += gf - ga

    return total / len(matches)


def _form_score(matches: list[dict], team: str) -> float:
    if not matches:
        return 0.0

    score = 0.0

    for match in matches:
        result = _result_for_team(match, team)
        gf, ga = _goals_for_against(match, team)

        if result == "W":
            score += 3
        elif result == "D":
            score += 1

        score += (gf * 0.15) - (ga * 0.1)

    return score / len(matches)


def _current_streak(matches: list[dict], team: str) -> float:
    if not matches:
        return 0.0

    streak = 0

    for match in reversed(matches):
        result = _result_for_team(match, team)

        if result == "W":
            if streak >= 0:
                streak += 1
            else:
                break
        elif result == "L":
            if streak <= 0:
                streak -= 1
            else:
                break
        else:
            break

    return float(streak)


def _team_profile(matches: list[dict], team: str) -> dict[str, float]:
    if not matches:
        return {
            "goals_for_avg": 0.0,
            "goals_against_avg": 0.0,
            "clean_sheet_rate": 0.0,
            "failed_to_score_rate": 0.0,
            "btts_rate": 0.0,
            "over_2_5_rate": 0.0,
            "corner_avg": 0.0,
            "sot_avg": 0.0,
        }

    goals_for = []
    goals_against = []
    clean_sheets = 0
    failed_to_score = 0
    btts = 0
    over_2_5 = 0
    corners = []
    sot = []

    for match in matches:
        gf, ga = _goals_for_against(match, team)

        goals_for.append(gf)
        goals_against.append(ga)

        if ga == 0:
            clean_sheets += 1

        if gf == 0:
            failed_to_score += 1

        if gf > 0 and ga > 0:
            btts += 1

        if gf + ga > 2.5:
            over_2_5 += 1

        if match["home_team"] == team:
            corners.append(match["home_corners"])
            sot.append(match["home_sot"])
        else:
            corners.append(match["away_corners"])
            sot.append(match["away_sot"])

    games = len(matches)

    return {
        "goals_for_avg": sum(goals_for) / games,
        "goals_against_avg": sum(goals_against) / games,
        "clean_sheet_rate": clean_sheets / games,
        "failed_to_score_rate": failed_to_score / games,
        "btts_rate": btts / games,
        "over_2_5_rate": over_2_5 / games,
        "corner_avg": sum(corners) / games,
        "sot_avg": sum(sot) / games,
    }


def _team_strength(matches: list[dict], team: str) -> float:
    profile = _team_profile(matches, team)

    return (
        _win_rate(matches, team)
        + _goal_diff(matches, team)
        + _form_score(matches, team)
        + profile["goals_for_avg"]
        + profile["clean_sheet_rate"]
        - profile["failed_to_score_rate"]
        - profile["goals_against_avg"]
    )


def _h2h_features(matches: list[dict], home: str, away: str) -> dict[str, float]:
    if not matches:
        return {
            "home_h2h_win_rate": 0.0,
            "away_h2h_win_rate": 0.0,
            "h2h_avg_goals": 0.0,
            "h2h_over_2_5_rate": 0.0,
        }

    home_wins = 0
    away_wins = 0
    total_goals = 0.0
    over_2_5 = 0

    for match in matches:
        total = match["home_goals"] + match["away_goals"]
        total_goals += total

        if total > 2.5:
            over_2_5 += 1

        if _result_for_team(match, home) == "W":
            home_wins += 1

        if _result_for_team(match, away) == "W":
            away_wins += 1

    games = len(matches)

    return {
        "home_h2h_win_rate": home_wins / games,
        "away_h2h_win_rate": away_wins / games,
        "h2h_avg_goals": total_goals / games,
        "h2h_over_2_5_rate": over_2_5 / games,
    }


def _league_profile(matches: list[dict]) -> dict[str, float]:
    if not matches:
        return {
            "league_home_win_rate": 0.0,
            "league_away_win_rate": 0.0,
            "league_draw_rate": 0.0,
            "league_avg_goals": 0.0,
            "league_btts_rate": 0.0,
            "league_over_2_5_rate": 0.0,
            "league_avg_corners": 0.0,
            "league_avg_sot": 0.0,
        }

    games = len(matches)

    home_wins = sum(1 for m in matches if m["home_goals"] > m["away_goals"])
    away_wins = sum(1 for m in matches if m["away_goals"] > m["home_goals"])
    draws = sum(1 for m in matches if m["home_goals"] == m["away_goals"])

    total_goals = [m["home_goals"] + m["away_goals"] for m in matches]
    total_corners = [m["home_corners"] + m["away_corners"] for m in matches]
    total_sot = [m["home_sot"] + m["away_sot"] for m in matches]

    btts = sum(1 for m in matches if m["home_goals"] > 0 and m["away_goals"] > 0)
    over_2_5 = sum(1 for m in matches if m["home_goals"] + m["away_goals"] > 2.5)

    return {
        "league_home_win_rate": home_wins / games,
        "league_away_win_rate": away_wins / games,
        "league_draw_rate": draws / games,
        "league_avg_goals": sum(total_goals) / games,
        "league_btts_rate": btts / games,
        "league_over_2_5_rate": over_2_5 / games,
        "league_avg_corners": sum(total_corners) / games,
        "league_avg_sot": sum(total_sot) / games,
    }