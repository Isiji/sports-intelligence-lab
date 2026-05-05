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
    ]


def load_training_frame(session: Session) -> pd.DataFrame:
    query = text(
        """
        SELECT
            m.id AS match_id,
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
        WHERE m.home_goals IS NOT NULL
          AND m.away_goals IS NOT NULL
        ORDER BY m.kickoff_date
        """
    )

    df = pd.read_sql(query, session.bind)

    if df.empty:
        return df

    df["target_home_win"] = (df["home_goals"] > df["away_goals"]).astype(int)

    return df


def load_upcoming_frame(session: Session, limit: int = 16) -> pd.DataFrame:
    query = text(
        """
        SELECT
            m.id AS match_id,

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
        WHERE m.home_goals IS NULL
          AND m.away_goals IS NULL
        ORDER BY m.kickoff_date
        LIMIT :limit
        """
    )

    return pd.read_sql(query, session.bind, params={"limit": limit})