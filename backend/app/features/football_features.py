# backend/app/features/football_features.py

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


INITIAL_ELO = 1500.0
K_FACTOR = 32.0
HOME_ADVANTAGE_ELO = 60.0


def feature_columns() -> list[str]:
    return [
        "home_sot",
        "home_corners",
        "home_possession",
        "home_fouls",
        "home_cards",
        "home_keeper_saves",
        "away_sot",
        "away_corners",
        "away_possession",
        "away_fouls",
        "away_cards",
        "away_keeper_saves",

        "home_win_rate",
        "away_win_rate",
        "home_goal_diff",
        "away_goal_diff",
        "home_form_score",
        "away_form_score",

        "home_h2h_win_rate",
        "away_h2h_win_rate",
        "h2h_avg_goals",
        "h2h_over_2_5_rate",

        "home_home_win_rate",
        "away_away_win_rate",
        "home_current_streak",
        "away_current_streak",

        "home_goals_for_avg",
        "home_goals_against_avg",
        "away_goals_for_avg",
        "away_goals_against_avg",

        "home_clean_sheet_rate",
        "away_clean_sheet_rate",
        "home_failed_to_score_rate",
        "away_failed_to_score_rate",

        "home_btts_rate",
        "away_btts_rate",
        "home_over_2_5_rate",
        "away_over_2_5_rate",

        "home_corner_avg",
        "away_corner_avg",
        "home_sot_avg",
        "away_sot_avg",

        "home_elo",
        "away_elo",
        "elo_diff",
        "home_elo_form",
        "away_elo_form",
        "elo_form_diff",
        "home_attack_elo",
        "away_attack_elo",
        "home_defense_elo",
        "away_defense_elo",
        "attack_defense_diff",
        "team_strength_diff",
    ]


MARKET_TARGETS = {
    "home_win": "target_home_win",
    "away_win": "target_away_win",
    "draw": "target_draw",
    "double_chance_1x": "target_double_chance_1x",
    "double_chance_x2": "target_double_chance_x2",
    "double_chance_12": "target_double_chance_12",
    "over_2_5_goals": "target_over_2_5",
    "under_2_5_goals": "target_under_2_5",
    "btts_yes": "target_btts_yes",
    "btts_no": "target_btts_no",
    "corners_over_8_5": "target_corners_over_8_5",
    "shots_on_target_over_8_5": "target_sot_over_8_5",
}


MARKET_LABELS = {
    "home_win": ("HOME_WIN", "NOT_HOME_WIN"),
    "away_win": ("AWAY_WIN", "NOT_AWAY_WIN"),
    "draw": ("DRAW", "NOT_DRAW"),
    "double_chance_1x": ("DOUBLE_CHANCE_1X", "NOT_DOUBLE_CHANCE_1X"),
    "double_chance_x2": ("DOUBLE_CHANCE_X2", "NOT_DOUBLE_CHANCE_X2"),
    "double_chance_12": ("DOUBLE_CHANCE_12", "NOT_DOUBLE_CHANCE_12"),
    "over_2_5_goals": ("OVER_2_5", "UNDER_2_5"),
    "under_2_5_goals": ("UNDER_2_5", "OVER_2_5"),
    "btts_yes": ("BTTS_YES", "BTTS_NO"),
    "btts_no": ("BTTS_NO", "BTTS_YES"),
    "corners_over_8_5": ("CORNERS_OVER_8_5", "CORNERS_UNDER_8_5"),
    "shots_on_target_over_8_5": ("SOT_OVER_8_5", "SOT_UNDER_8_5"),
}


def load_training_frame(session: Session) -> pd.DataFrame:
    df = _base_query(session)

    if df.empty:
        return df

    df = _add_advanced_features(df)
    df = _add_targets(df)

    return df


def load_upcoming_frame(session: Session, limit: int = 30) -> pd.DataFrame:
    df = _base_query(session, upcoming_only=True, limit=limit)

    if df.empty:
        return df

    df = _add_advanced_features(df)

    return df


def _base_query(session: Session, upcoming_only: bool = False, limit: int | None = None):
    query = text(
        """
        SELECT
            m.id AS match_id,
            m.kickoff_date,
            m.league,
            m.home_team,
            m.away_team,
            m.home_goals,
            m.away_goals,

            hs.shots_on_target AS home_sot,
            hs.corners AS home_corners,
            hs.possession AS home_possession,
            hs.fouls AS home_fouls,
            hs.cards AS home_cards,
            hs.keeper_saves AS home_keeper_saves,

            as1.shots_on_target AS away_sot,
            as1.corners AS away_corners,
            as1.possession AS away_possession,
            as1.fouls AS away_fouls,
            as1.cards AS away_cards,
            as1.keeper_saves AS away_keeper_saves

        FROM matches m
        JOIN team_match_stats hs ON hs.match_id = m.id AND hs.is_home = 1
        JOIN team_match_stats as1 ON as1.match_id = m.id AND as1.is_home = 0
        ORDER BY m.kickoff_date ASC, m.id ASC
        """
    )

    df = pd.read_sql(query, session.bind)
    df["kickoff_date"] = pd.to_datetime(df["kickoff_date"])

    if upcoming_only:
        df = df[df["home_goals"].isna() & df["away_goals"].isna()]
        if limit:
            df = df.head(limit)
    else:
        df = df[df["home_goals"].notna() & df["away_goals"].notna()]

    return df.reset_index(drop=True)


def _add_targets(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    total_goals = df["home_goals"] + df["away_goals"]
    total_corners = df["home_corners"] + df["away_corners"]
    total_sot = df["home_sot"] + df["away_sot"]

    df["target_home_win"] = (df["home_goals"] > df["away_goals"]).astype(int)
    df["target_away_win"] = (df["away_goals"] > df["home_goals"]).astype(int)
    df["target_draw"] = (df["home_goals"] == df["away_goals"]).astype(int)

    df["target_double_chance_1x"] = (df["home_goals"] >= df["away_goals"]).astype(int)
    df["target_double_chance_x2"] = (df["away_goals"] >= df["home_goals"]).astype(int)
    df["target_double_chance_12"] = (df["home_goals"] != df["away_goals"]).astype(int)

    df["target_over_2_5"] = (total_goals > 2.5).astype(int)
    df["target_under_2_5"] = (total_goals <= 2.5).astype(int)

    df["target_btts_yes"] = ((df["home_goals"] > 0) & (df["away_goals"] > 0)).astype(int)
    df["target_btts_no"] = ((df["home_goals"] == 0) | (df["away_goals"] == 0)).astype(int)

    df["target_corners_over_8_5"] = (total_corners > 8.5).astype(int)
    df["target_sot_over_8_5"] = (total_sot > 8.5).astype(int)

    return df


def _add_advanced_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.sort_values(["kickoff_date", "match_id"]).reset_index(drop=True)

    for col in feature_columns():
        if col not in df.columns:
            df[col] = 0.0

    elo: dict[str, float] = {}
    attack_elo: dict[str, float] = {}
    defense_elo: dict[str, float] = {}
    elo_history: dict[str, list[float]] = {}

    for i, row in df.iterrows():
        home = row["home_team"]
        away = row["away_team"]
        date = row["kickoff_date"]

        home_elo = elo.get(home, INITIAL_ELO)
        away_elo = elo.get(away, INITIAL_ELO)

        home_attack = attack_elo.get(home, INITIAL_ELO)
        away_attack = attack_elo.get(away, INITIAL_ELO)

        home_defense = defense_elo.get(home, INITIAL_ELO)
        away_defense = defense_elo.get(away, INITIAL_ELO)

        home_elo_form = _elo_form(elo_history.get(home, []), home_elo)
        away_elo_form = _elo_form(elo_history.get(away, []), away_elo)

        df.at[i, "home_elo"] = home_elo
        df.at[i, "away_elo"] = away_elo
        df.at[i, "elo_diff"] = (home_elo + HOME_ADVANTAGE_ELO) - away_elo

        df.at[i, "home_elo_form"] = home_elo_form
        df.at[i, "away_elo_form"] = away_elo_form
        df.at[i, "elo_form_diff"] = home_elo_form - away_elo_form

        df.at[i, "home_attack_elo"] = home_attack
        df.at[i, "away_attack_elo"] = away_attack
        df.at[i, "home_defense_elo"] = home_defense
        df.at[i, "away_defense_elo"] = away_defense

        df.at[i, "attack_defense_diff"] = home_attack - away_defense

        home_hist = _team_history(df, home, date).tail(8)
        away_hist = _team_history(df, away, date).tail(8)

        df.at[i, "home_win_rate"] = _win_rate(home_hist, home)
        df.at[i, "away_win_rate"] = _win_rate(away_hist, away)

        df.at[i, "home_goal_diff"] = _goal_diff(home_hist, home)
        df.at[i, "away_goal_diff"] = _goal_diff(away_hist, away)

        df.at[i, "home_form_score"] = _form_score(home_hist, home)
        df.at[i, "away_form_score"] = _form_score(away_hist, away)

        h2h = _head_to_head_history(df, home, away, date).tail(6)

        for key, value in _h2h_features(h2h, home, away).items():
            df.at[i, key] = value

        home_home_hist = df[(df["home_team"] == home) & (df["kickoff_date"] < date)].tail(8)
        away_away_hist = df[(df["away_team"] == away) & (df["kickoff_date"] < date)].tail(8)

        df.at[i, "home_home_win_rate"] = _home_win_rate(home_home_hist, home)
        df.at[i, "away_away_win_rate"] = _away_win_rate(away_away_hist, away)

        df.at[i, "home_current_streak"] = _current_streak(home_hist, home)
        df.at[i, "away_current_streak"] = _current_streak(away_hist, away)

        for key, value in _team_profile(home_hist, home).items():
            df.at[i, f"home_{key}"] = value

        for key, value in _team_profile(away_hist, away).items():
            df.at[i, f"away_{key}"] = value

        home_strength = _team_strength(home_hist, home)
        away_strength = _team_strength(away_hist, away)
        df.at[i, "team_strength_diff"] = home_strength - away_strength

        if pd.notna(row["home_goals"]) and pd.notna(row["away_goals"]):
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

            elo_history.setdefault(home, []).append(home_elo)
            elo_history.setdefault(away, []).append(away_elo)

            elo[home] = new_home_elo
            elo[away] = new_away_elo

            attack_elo[home] = new_home_attack
            defense_elo[away] = new_away_defense

            attack_elo[away] = new_away_attack
            defense_elo[home] = new_home_defense

    return df.fillna(0.0)


def _elo_form(history: list[float], current_elo: float) -> float:
    if not history:
        return 0.0

    recent = history[-5:]

    return current_elo - (sum(recent) / len(recent))


def _update_result_elo(
    home_elo: float,
    away_elo: float,
    home_goals: float,
    away_goals: float,
) -> tuple[float, float]:
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


def _update_attack_defense_elo(
    attack_rating: float,
    defense_rating: float,
    goals_scored: float,
) -> tuple[float, float]:
    expected_goals = 1.35
    performance = goals_scored - expected_goals

    movement = max(min(performance * 10, 24), -24)

    new_attack = attack_rating + movement
    new_defense = defense_rating - movement

    return new_attack, new_defense


def _team_history(df: pd.DataFrame, team: str, date) -> pd.DataFrame:
    return df[
        ((df["home_team"] == team) | (df["away_team"] == team))
        & (df["kickoff_date"] < date)
        & df["home_goals"].notna()
        & df["away_goals"].notna()
    ]


def _head_to_head_history(df: pd.DataFrame, home: str, away: str, date) -> pd.DataFrame:
    return df[
        (
            ((df["home_team"] == home) & (df["away_team"] == away))
            | ((df["home_team"] == away) & (df["away_team"] == home))
        )
        & (df["kickoff_date"] < date)
        & df["home_goals"].notna()
        & df["away_goals"].notna()
    ]


def _win_rate(hist: pd.DataFrame, team: str) -> float:
    wins = 0

    for _, r in hist.iterrows():
        if _result_for_team(r, team) == "W":
            wins += 1

    return wins / max(len(hist), 1)


def _home_win_rate(hist: pd.DataFrame, team: str) -> float:
    wins = 0

    for _, r in hist.iterrows():
        if r["home_team"] == team and r["home_goals"] > r["away_goals"]:
            wins += 1

    return wins / max(len(hist), 1)


def _away_win_rate(hist: pd.DataFrame, team: str) -> float:
    wins = 0

    for _, r in hist.iterrows():
        if r["away_team"] == team and r["away_goals"] > r["home_goals"]:
            wins += 1

    return wins / max(len(hist), 1)


def _goal_diff(hist: pd.DataFrame, team: str) -> float:
    diff = 0.0

    for _, r in hist.iterrows():
        gf, ga = _goals_for_against(r, team)
        diff += gf - ga

    return diff / max(len(hist), 1)


def _form_score(hist: pd.DataFrame, team: str) -> float:
    score = 0.0

    for _, r in hist.iterrows():
        result = _result_for_team(r, team)
        gf, ga = _goals_for_against(r, team)

        if result == "W":
            score += 3
        elif result == "D":
            score += 1

        score += (gf * 0.15) - (ga * 0.1)

    return score / max(len(hist), 1)


def _current_streak(hist: pd.DataFrame, team: str) -> float:
    if hist.empty:
        return 0.0

    streak = 0

    for _, r in hist.sort_values("kickoff_date", ascending=False).iterrows():
        result = _result_for_team(r, team)

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


def _team_profile(hist: pd.DataFrame, team: str) -> dict[str, float]:
    goals_for = []
    goals_against = []
    clean_sheets = 0
    failed_to_score = 0
    btts = 0
    over_2_5 = 0
    corners = []
    sot = []

    for _, r in hist.iterrows():
        gf, ga = _goals_for_against(r, team)

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

        if r["home_team"] == team:
            corners.append(float(r["home_corners"] or 0))
            sot.append(float(r["home_sot"] or 0))
        else:
            corners.append(float(r["away_corners"] or 0))
            sot.append(float(r["away_sot"] or 0))

    games = max(len(hist), 1)

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


def _team_strength(hist: pd.DataFrame, team: str) -> float:
    profile = _team_profile(hist, team)

    return (
        _win_rate(hist, team)
        + _goal_diff(hist, team)
        + _form_score(hist, team)
        + profile["goals_for_avg"]
        + profile["clean_sheet_rate"]
        - profile["failed_to_score_rate"]
        - profile["goals_against_avg"]
    )


def _h2h_features(hist: pd.DataFrame, home: str, away: str) -> dict[str, float]:
    home_wins = 0
    away_wins = 0
    total_goals = 0.0
    over_2_5 = 0

    for _, r in hist.iterrows():
        home_goals = float(r["home_goals"] or 0)
        away_goals = float(r["away_goals"] or 0)

        total_goals += home_goals + away_goals

        if home_goals + away_goals > 2.5:
            over_2_5 += 1

        if r["home_team"] == home:
            if home_goals > away_goals:
                home_wins += 1
            elif away_goals > home_goals:
                away_wins += 1
        else:
            if away_goals > home_goals:
                home_wins += 1
            elif home_goals > away_goals:
                away_wins += 1

    games = max(len(hist), 1)

    return {
        "home_h2h_win_rate": home_wins / games,
        "away_h2h_win_rate": away_wins / games,
        "h2h_avg_goals": total_goals / games,
        "h2h_over_2_5_rate": over_2_5 / games,
    }


def _result_for_team(row, team: str) -> str:
    if row["home_team"] == team:
        if row["home_goals"] > row["away_goals"]:
            return "W"
        if row["home_goals"] < row["away_goals"]:
            return "L"
        return "D"

    if row["away_team"] == team:
        if row["away_goals"] > row["home_goals"]:
            return "W"
        if row["away_goals"] < row["home_goals"]:
            return "L"
        return "D"

    return "D"


def _goals_for_against(row, team: str) -> tuple[float, float]:
    if row["home_team"] == team:
        return float(row["home_goals"] or 0), float(row["away_goals"] or 0)

    return float(row["away_goals"] or 0), float(row["home_goals"] or 0)