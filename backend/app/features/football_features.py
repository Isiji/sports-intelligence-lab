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

        # upgraded features
        "home_win_rate",
        "away_win_rate",
        "home_goal_diff",
        "away_goal_diff",
        "home_form_score",
        "away_form_score",
        
        # ADD THESE
        "home_h2h_win_rate",
        "away_h2h_win_rate",
        "h2h_avg_goals",
        "h2h_over_2_5_rate",
    ]


# ---------------- TRAINING ----------------

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


# ---------------- BASE QUERY ----------------

def _base_query(session: Session, upcoming_only=False, limit=None):
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
        df = df[df["home_goals"].isna()]
        if limit:
            df = df.head(limit)
    else:
        df = df[df["home_goals"].notna()]

    return df


# ---------------- FEATURE ENGINE ----------------

def _add_advanced_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # existing features
    df["home_win_rate"] = 0.0
    df["away_win_rate"] = 0.0
    df["home_goal_diff"] = 0.0
    df["away_goal_diff"] = 0.0
    df["home_form_score"] = 0.0
    df["away_form_score"] = 0.0

    # NEW H2H features
    df["home_h2h_win_rate"] = 0.0
    df["away_h2h_win_rate"] = 0.0
    df["h2h_avg_goals"] = 0.0
    df["h2h_over_2_5_rate"] = 0.0

    for i, row in df.iterrows():
        home = row["home_team"]
        away = row["away_team"]
        date = row["kickoff_date"]

        # -------- FORM HISTORY --------
        home_hist = df[
            ((df["home_team"] == home) | (df["away_team"] == home))
            & (df["kickoff_date"] < date)
        ].tail(5)

        away_hist = df[
            ((df["home_team"] == away) | (df["away_team"] == away))
            & (df["kickoff_date"] < date)
        ].tail(5)

        df.at[i, "home_win_rate"] = _win_rate(home_hist, home)
        df.at[i, "away_win_rate"] = _win_rate(away_hist, away)

        df.at[i, "home_goal_diff"] = _goal_diff(home_hist, home)
        df.at[i, "away_goal_diff"] = _goal_diff(away_hist, away)

        df.at[i, "home_form_score"] = _form_score(home_hist, home)
        df.at[i, "away_form_score"] = _form_score(away_hist, away)

        # -------- HEAD-TO-HEAD --------
        h2h = df[
            (
                ((df["home_team"] == home) & (df["away_team"] == away)) |
                ((df["home_team"] == away) & (df["away_team"] == home))
            )
            & (df["kickoff_date"] < date)
        ].tail(5)

        home_wins = 0
        away_wins = 0
        total_goals = 0
        over_2_5 = 0

        for _, r in h2h.iterrows():
            hg = r["home_goals"] or 0
            ag = r["away_goals"] or 0

            total_goals += hg + ag

            if hg + ag > 2:
                over_2_5 += 1

            # determine who was home/away in that match
            if r["home_team"] == home:
                if hg > ag:
                    home_wins += 1
                elif ag > hg:
                    away_wins += 1
            else:
                if ag > hg:
                    home_wins += 1
                elif hg > ag:
                    away_wins += 1

        games = max(len(h2h), 1)

        df.at[i, "home_h2h_win_rate"] = home_wins / games
        df.at[i, "away_h2h_win_rate"] = away_wins / games
        df.at[i, "h2h_avg_goals"] = total_goals / games
        df.at[i, "h2h_over_2_5_rate"] = over_2_5 / games

    return df.fillna(0.0)

# ---------------- CALCULATIONS ----------------

def _win_rate(hist: pd.DataFrame, team: str) -> float:
    wins = 0
    for _, r in hist.iterrows():
        if r["home_team"] == team:
            if r["home_goals"] > r["away_goals"]:
                wins += 1
        else:
            if r["away_goals"] > r["home_goals"]:
                wins += 1
    return wins / max(len(hist), 1)


def _goal_diff(hist: pd.DataFrame, team: str) -> float:
    diff = 0
    for _, r in hist.iterrows():
        if r["home_team"] == team:
            diff += (r["home_goals"] or 0) - (r["away_goals"] or 0)
        else:
            diff += (r["away_goals"] or 0) - (r["home_goals"] or 0)
    return diff / max(len(hist), 1)


def _form_score(hist: pd.DataFrame, team: str) -> float:
    score = 0
    for _, r in hist.iterrows():
        if r["home_team"] == team:
            g_for = r["home_goals"] or 0
            g_against = r["away_goals"] or 0
        else:
            g_for = r["away_goals"] or 0
            g_against = r["home_goals"] or 0

        score += (g_for * 2) - g_against

    return score / max(len(hist), 1)