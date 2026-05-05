# backend/app/features/football_features.py

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


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
        "team_strength_diff",
    ]


def load_training_frame(session: Session) -> pd.DataFrame:
    df = _base_query(session)

    if df.empty:
        return df

    df = _add_advanced_features(df)

    df["target_home_win"] = (df["home_goals"] > df["away_goals"]).astype(int)

    total_goals = df["home_goals"] + df["away_goals"]
    df["target_over_2_5"] = (total_goals > 2.5).astype(int)

    return df


def load_upcoming_frame(session: Session, limit: int = 16) -> pd.DataFrame:
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
        ORDER BY m.kickoff_date
        """
    )

    df = pd.read_sql(query, session.bind)

    if upcoming_only:
        df = df[df["home_goals"].isna() & df["away_goals"].isna()]
        if limit:
            df = df.head(limit)
    else:
        df = df[df["home_goals"].notna() & df["away_goals"].notna()]

    return df


def _add_advanced_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    new_columns = [
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
        "team_strength_diff",
    ]

    for column in new_columns:
        df[column] = 0.0

    for i, row in df.iterrows():
        home = row["home_team"]
        away = row["away_team"]
        date = row["kickoff_date"]

        home_hist = _team_history(df, home, date).tail(5)
        away_hist = _team_history(df, away, date).tail(5)

        df.at[i, "home_win_rate"] = _win_rate(home_hist, home)
        df.at[i, "away_win_rate"] = _win_rate(away_hist, away)

        df.at[i, "home_goal_diff"] = _goal_diff(home_hist, home)
        df.at[i, "away_goal_diff"] = _goal_diff(away_hist, away)

        df.at[i, "home_form_score"] = _form_score(home_hist, home)
        df.at[i, "away_form_score"] = _form_score(away_hist, away)

        h2h = _head_to_head_history(df, home, away, date).tail(5)
        h2h_values = _h2h_features(h2h, home, away)

        df.at[i, "home_h2h_win_rate"] = h2h_values["home_h2h_win_rate"]
        df.at[i, "away_h2h_win_rate"] = h2h_values["away_h2h_win_rate"]
        df.at[i, "h2h_avg_goals"] = h2h_values["h2h_avg_goals"]
        df.at[i, "h2h_over_2_5_rate"] = h2h_values["h2h_over_2_5_rate"]

        home_home_hist = df[
            (df["home_team"] == home)
            & (df["kickoff_date"] < date)
        ].tail(5)

        away_away_hist = df[
            (df["away_team"] == away)
            & (df["kickoff_date"] < date)
        ].tail(5)

        df.at[i, "home_home_win_rate"] = _home_win_rate(home_home_hist, home)
        df.at[i, "away_away_win_rate"] = _away_win_rate(away_away_hist, away)

        df.at[i, "home_current_streak"] = _current_streak(home_hist, home)
        df.at[i, "away_current_streak"] = _current_streak(away_hist, away)

        home_strength = _team_strength(home_hist, home)
        away_strength = _team_strength(away_hist, away)
        df.at[i, "team_strength_diff"] = home_strength - away_strength

    return df.fillna(0.0)


def _team_history(df: pd.DataFrame, team: str, date) -> pd.DataFrame:
    return df[
        ((df["home_team"] == team) | (df["away_team"] == team))
        & (df["kickoff_date"] < date)
    ]


def _head_to_head_history(df: pd.DataFrame, home: str, away: str, date) -> pd.DataFrame:
    return df[
        (
            ((df["home_team"] == home) & (df["away_team"] == away))
            | ((df["home_team"] == away) & (df["away_team"] == home))
        )
        & (df["kickoff_date"] < date)
    ]


def _win_rate(hist: pd.DataFrame, team: str) -> float:
    wins = 0

    for _, r in hist.iterrows():
        if r["home_team"] == team and r["home_goals"] > r["away_goals"]:
            wins += 1
        elif r["away_team"] == team and r["away_goals"] > r["home_goals"]:
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
        if r["home_team"] == team:
            diff += float(r["home_goals"] or 0) - float(r["away_goals"] or 0)
        else:
            diff += float(r["away_goals"] or 0) - float(r["home_goals"] or 0)

    return diff / max(len(hist), 1)


def _form_score(hist: pd.DataFrame, team: str) -> float:
    score = 0.0

    for _, r in hist.iterrows():
        if r["home_team"] == team:
            goals_for = float(r["home_goals"] or 0)
            goals_against = float(r["away_goals"] or 0)
        else:
            goals_for = float(r["away_goals"] or 0)
            goals_against = float(r["home_goals"] or 0)

        score += (goals_for * 2) - goals_against

    return score / max(len(hist), 1)


def _current_streak(hist: pd.DataFrame, team: str) -> float:
    """
    Positive number = winning streak.
    Negative number = losing streak.
    Zero = no active win/loss streak or draw.
    """

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


def _team_strength(hist: pd.DataFrame, team: str) -> float:
    """
    Simple strength score:
    win_rate + goal_difference + form_score.
    Later we can replace this with ELO.
    """

    return (
        _win_rate(hist, team)
        + _goal_diff(hist, team)
        + _form_score(hist, team)
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

        if home_goals + away_goals > 2:
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