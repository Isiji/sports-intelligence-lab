# backend/app/features/football_features.py

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


def feature_columns() -> list[str]:
    return [
        # base stats
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

        # NEW: form features
        "home_form_goals_scored",
        "home_form_goals_conceded",
        "away_form_goals_scored",
        "away_form_goals_conceded",
    ]


def load_training_frame(session: Session) -> pd.DataFrame:
    df = _base_query(session)

    if df.empty:
        return df

    df = _add_form_features(df)

    df["target_home_win"] = (df["home_goals"] > df["away_goals"]).astype(int)

    total_goals = df["home_goals"] + df["away_goals"]
    df["target_over_2_5"] = (total_goals > 2.5).astype(int)

    return df


def load_upcoming_frame(session: Session, limit: int = 16) -> pd.DataFrame:
    df = _base_query(session, upcoming_only=True, limit=limit)

    if df.empty:
        return df

    df = _add_form_features(df)

    return df


# ---------- INTERNAL HELPERS ----------

def _base_query(session: Session, upcoming_only: bool = False, limit: int | None = None) -> pd.DataFrame:
    query = text(
        """
        SELECT
            m.id AS match_id,
            m.kickoff_date,
            m.home_team,
            m.away_team,
            m.home_goals,
            m.away_goals,

            home_stats.shots_on_target AS home_sot,
            home_stats.corners AS home_corners,
            home_stats.possession AS home_possession,
            home_stats.fouls AS home_fouls,
            home_stats.cards AS home_cards,
            home_stats.keeper_saves AS home_keeper_saves,

            away_stats.shots_on_target AS away_sot,
            away_stats.corners AS away_corners,
            away_stats.possession AS away_possession,
            away_stats.fouls AS away_fouls,
            away_stats.cards AS away_cards,
            away_stats.keeper_saves AS away_keeper_saves

        FROM matches m
        JOIN team_match_stats home_stats
            ON home_stats.match_id = m.id AND home_stats.is_home = 1
        JOIN team_match_stats away_stats
            ON away_stats.match_id = m.id AND away_stats.is_home = 0
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


def _add_form_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute rolling form (last 5 matches) for each team.
    """

    df = df.copy()

    df["home_form_goals_scored"] = 0.0
    df["home_form_goals_conceded"] = 0.0
    df["away_form_goals_scored"] = 0.0
    df["away_form_goals_conceded"] = 0.0

    for idx, row in df.iterrows():
        home_team = row["home_team"]
        away_team = row["away_team"]
        current_date = row["kickoff_date"]

        home_history = df[
            (
                ((df["home_team"] == home_team) | (df["away_team"] == home_team))
                & (df["kickoff_date"] < current_date)
            )
        ].tail(5)

        away_history = df[
            (
                ((df["home_team"] == away_team) | (df["away_team"] == away_team))
                & (df["kickoff_date"] < current_date)
            )
        ].tail(5)

        df.at[idx, "home_form_goals_scored"] = _goals_scored(home_history, home_team)
        df.at[idx, "home_form_goals_conceded"] = _goals_conceded(home_history, home_team)

        df.at[idx, "away_form_goals_scored"] = _goals_scored(away_history, away_team)
        df.at[idx, "away_form_goals_conceded"] = _goals_conceded(away_history, away_team)
    df = df.fillna(0.0)
    return df


def _goals_scored(history: pd.DataFrame, team: str) -> float:
    total = 0
    for _, row in history.iterrows():
        if row["home_team"] == team:
            total += row["home_goals"] or 0
        else:
            total += row["away_goals"] or 0
    return total / max(len(history), 1)


def _goals_conceded(history: pd.DataFrame, team: str) -> float:
    total = 0
    for _, row in history.iterrows():
        if row["home_team"] == team:
            total += row["away_goals"] or 0
        else:
            total += row["home_goals"] or 0
    return total / max(len(history), 1)