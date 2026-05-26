# backend/app/features/football_features.py

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


INITIAL_ELO = 1500.0
K_FACTOR = 32.0
HOME_ADVANTAGE_ELO = 60.0


TOURNAMENT_KNOCKOUT_STAGES = {
    "knockout",
    "round_of_16",
    "quarterfinal",
    "semifinal",
    "final",
    "playoff",
}


def feature_columns() -> list[str]:
    return [
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

        "league_home_win_rate",
        "league_away_win_rate",
        "league_draw_rate",
        "league_avg_goals",
        "league_btts_rate",
        "league_over_2_5_rate",
        "league_avg_corners",
        "league_avg_sot",

        "is_international",
        "is_neutral_venue",
        "is_knockout",
        "is_final",
        "is_semifinal",
        "is_qualifier",
        "is_friendly",
        "competition_priority",
        "tournament_pressure_score",
    ]


MARKET_TARGETS = {
    "home_win": "target_home_win",
    "away_win": "target_away_win",
    "draw": "target_draw",

    "double_chance_1x": "target_double_chance_1x",
    "double_chance_x2": "target_double_chance_x2",
    "double_chance_12": "target_double_chance_12",

    "over_1_5_goals": "target_over_1_5",
    "under_1_5_goals": "target_under_1_5",
    "over_2_5_goals": "target_over_2_5",
    "under_2_5_goals": "target_under_2_5",
    "over_3_5_goals": "target_over_3_5",
    "under_3_5_goals": "target_under_3_5",

    "btts_yes": "target_btts_yes",
    "btts_no": "target_btts_no",

    "home_over_0_5_goals": "target_home_over_0_5",
    "away_over_0_5_goals": "target_away_over_0_5",
    "home_clean_sheet": "target_home_clean_sheet",
    "away_clean_sheet": "target_away_clean_sheet",

    "corners_over_8_5": "target_corners_over_8_5",
    "shots_on_target_over_8_5": "target_sot_over_8_5",

    "draw_no_bet_home": "target_draw_no_bet_home",
    "draw_no_bet_away": "target_draw_no_bet_away",
    "home_win_to_nil": "target_home_win_to_nil",
    "away_win_to_nil": "target_away_win_to_nil",

    "asian_handicap_home_plus_0_5": "target_ah_home_plus_0_5",
    "asian_handicap_away_plus_0_5": "target_ah_away_plus_0_5",
    "asian_handicap_home_minus_0_5": "target_ah_home_minus_0_5",
    "asian_handicap_away_minus_0_5": "target_ah_away_minus_0_5",

    "asian_handicap_home_plus_1_5": "target_ah_home_plus_1_5",
    "asian_handicap_away_plus_1_5": "target_ah_away_plus_1_5",
    "asian_handicap_home_minus_1_5": "target_ah_home_minus_1_5",
    "asian_handicap_away_minus_1_5": "target_ah_away_minus_1_5",

    "home_away_home": "target_home_away_home",
    "home_away_away": "target_home_away_away",

    "handicap_result_home_plus_1_0": "target_handicap_result_home_plus_1_0",
    "handicap_result_draw_plus_1_0": "target_handicap_result_draw_plus_1_0",
    "handicap_result_away_plus_1_0": "target_handicap_result_away_plus_1_0",

    "handicap_result_home_minus_1_0": "target_handicap_result_home_minus_1_0",
    "handicap_result_draw_minus_1_0": "target_handicap_result_draw_minus_1_0",
    "handicap_result_away_minus_1_0": "target_handicap_result_away_minus_1_0",

    "result_total_home_over_1_5_goals": "target_result_total_home_over_1_5",
    "result_total_home_over_2_5_goals": "target_result_total_home_over_2_5",
    "result_total_home_over_3_5_goals": "target_result_total_home_over_3_5",

    "result_total_draw_over_1_5_goals": "target_result_total_draw_over_1_5",
    "result_total_draw_over_2_5_goals": "target_result_total_draw_over_2_5",
    "result_total_draw_over_3_5_goals": "target_result_total_draw_over_3_5",

    "result_total_away_over_1_5_goals": "target_result_total_away_over_1_5",
    "result_total_away_over_2_5_goals": "target_result_total_away_over_2_5",
    "result_total_away_over_3_5_goals": "target_result_total_away_over_3_5",
}


STATS_REQUIRED_MARKETS = {
    "corners_over_8_5",
    "shots_on_target_over_8_5",
}


MARKET_LABELS = {
    "home_win": ("HOME_WIN", "NOT_HOME_WIN"),
    "away_win": ("AWAY_WIN", "NOT_AWAY_WIN"),
    "draw": ("DRAW", "NOT_DRAW"),

    "double_chance_1x": ("DOUBLE_CHANCE_1X", "NOT_DOUBLE_CHANCE_1X"),
    "double_chance_x2": ("DOUBLE_CHANCE_X2", "NOT_DOUBLE_CHANCE_X2"),
    "double_chance_12": ("DOUBLE_CHANCE_12", "NOT_DOUBLE_CHANCE_12"),

    "over_1_5_goals": ("OVER_1_5", "UNDER_1_5"),
    "under_1_5_goals": ("UNDER_1_5", "OVER_1_5"),
    "over_2_5_goals": ("OVER_2_5", "UNDER_2_5"),
    "under_2_5_goals": ("UNDER_2_5", "OVER_2_5"),
    "over_3_5_goals": ("OVER_3_5", "UNDER_3_5"),
    "under_3_5_goals": ("UNDER_3_5", "OVER_3_5"),

    "btts_yes": ("BTTS_YES", "BTTS_NO"),
    "btts_no": ("BTTS_NO", "BTTS_YES"),

    "home_over_0_5_goals": ("HOME_OVER_0_5", "HOME_UNDER_0_5"),
    "away_over_0_5_goals": ("AWAY_OVER_0_5", "AWAY_UNDER_0_5"),
    "home_clean_sheet": ("HOME_CLEAN_SHEET", "HOME_CONCEDED"),
    "away_clean_sheet": ("AWAY_CLEAN_SHEET", "AWAY_CONCEDED"),

    "corners_over_8_5": ("CORNERS_OVER_8_5", "CORNERS_UNDER_8_5"),
    "shots_on_target_over_8_5": ("SOT_OVER_8_5", "SOT_UNDER_8_5"),

    "draw_no_bet_home": ("DRAW_NO_BET_HOME", "NOT_DRAW_NO_BET_HOME"),
    "draw_no_bet_away": ("DRAW_NO_BET_AWAY", "NOT_DRAW_NO_BET_AWAY"),
    "home_win_to_nil": ("HOME_WIN_TO_NIL", "NOT_HOME_WIN_TO_NIL"),
    "away_win_to_nil": ("AWAY_WIN_TO_NIL", "NOT_AWAY_WIN_TO_NIL"),

    "asian_handicap_home_plus_0_5": ("ASIAN_HANDICAP_HOME_PLUS_0_5", "NOT_ASIAN_HANDICAP_HOME_PLUS_0_5"),
    "asian_handicap_away_plus_0_5": ("ASIAN_HANDICAP_AWAY_PLUS_0_5", "NOT_ASIAN_HANDICAP_AWAY_PLUS_0_5"),
    "asian_handicap_home_minus_0_5": ("ASIAN_HANDICAP_HOME_MINUS_0_5", "NOT_ASIAN_HANDICAP_HOME_MINUS_0_5"),
    "asian_handicap_away_minus_0_5": ("ASIAN_HANDICAP_AWAY_MINUS_0_5", "NOT_ASIAN_HANDICAP_AWAY_MINUS_0_5"),

    "asian_handicap_home_plus_1_5": ("ASIAN_HANDICAP_HOME_PLUS_1_5", "NOT_ASIAN_HANDICAP_HOME_PLUS_1_5"),
    "asian_handicap_away_plus_1_5": ("ASIAN_HANDICAP_AWAY_PLUS_1_5", "NOT_ASIAN_HANDICAP_AWAY_PLUS_1_5"),
    "asian_handicap_home_minus_1_5": ("ASIAN_HANDICAP_HOME_MINUS_1_5", "NOT_ASIAN_HANDICAP_HOME_MINUS_1_5"),
    "asian_handicap_away_minus_1_5": ("ASIAN_HANDICAP_AWAY_MINUS_1_5", "NOT_ASIAN_HANDICAP_AWAY_MINUS_1_5"),

    "home_away_home": (
        "HOME_AWAY_HOME",
        "NOT_HOME_AWAY_HOME",
    ),

    "home_away_away": (
        "HOME_AWAY_AWAY",
        "NOT_HOME_AWAY_AWAY",
    ),

    "handicap_result_home_plus_1_0": (
        "HANDICAP_RESULT_HOME_PLUS_1_0",
        "NOT_HANDICAP_RESULT_HOME_PLUS_1_0",
    ),

    "handicap_result_draw_plus_1_0": (
        "HANDICAP_RESULT_DRAW_PLUS_1_0",
        "NOT_HANDICAP_RESULT_DRAW_PLUS_1_0",
    ),

    "handicap_result_away_plus_1_0": (
        "HANDICAP_RESULT_AWAY_PLUS_1_0",
        "NOT_HANDICAP_RESULT_AWAY_PLUS_1_0",
    ),

    "handicap_result_home_minus_1_0": (
        "HANDICAP_RESULT_HOME_MINUS_1_0",
        "NOT_HANDICAP_RESULT_HOME_MINUS_1_0",
    ),

    "handicap_result_draw_minus_1_0": (
        "HANDICAP_RESULT_DRAW_MINUS_1_0",
        "NOT_HANDICAP_RESULT_DRAW_MINUS_1_0",
    ),

    "handicap_result_away_minus_1_0": (
        "HANDICAP_RESULT_AWAY_MINUS_1_0",
        "NOT_HANDICAP_RESULT_AWAY_MINUS_1_0",
    ),

    "result_total_home_over_1_5_goals": (
        "RESULT_TOTAL_HOME_OVER_1_5",
        "NOT_RESULT_TOTAL_HOME_OVER_1_5",
    ),

    "result_total_home_over_2_5_goals": (
        "RESULT_TOTAL_HOME_OVER_2_5",
        "NOT_RESULT_TOTAL_HOME_OVER_2_5",
    ),

    "result_total_home_over_3_5_goals": (
        "RESULT_TOTAL_HOME_OVER_3_5",
        "NOT_RESULT_TOTAL_HOME_OVER_3_5",
    ),

    "result_total_draw_over_1_5_goals": (
        "RESULT_TOTAL_DRAW_OVER_1_5",
        "NOT_RESULT_TOTAL_DRAW_OVER_1_5",
    ),

    "result_total_draw_over_2_5_goals": (
        "RESULT_TOTAL_DRAW_OVER_2_5",
        "NOT_RESULT_TOTAL_DRAW_OVER_2_5",
    ),

    "result_total_draw_over_3_5_goals": (
        "RESULT_TOTAL_DRAW_OVER_3_5",
        "NOT_RESULT_TOTAL_DRAW_OVER_3_5",
    ),

    "result_total_away_over_1_5_goals": (
        "RESULT_TOTAL_AWAY_OVER_1_5",
        "NOT_RESULT_TOTAL_AWAY_OVER_1_5",
    ),

    "result_total_away_over_2_5_goals": (
        "RESULT_TOTAL_AWAY_OVER_2_5",
        "NOT_RESULT_TOTAL_AWAY_OVER_2_5",
    ),

    "result_total_away_over_3_5_goals": (
        "RESULT_TOTAL_AWAY_OVER_3_5",
        "NOT_RESULT_TOTAL_AWAY_OVER_3_5",
    ),
}


def load_training_frame(session: Session) -> pd.DataFrame:
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
            m.has_stats,

            COALESCE(m.is_international, false) AS is_international,
            COALESCE(m.is_neutral_venue, false) AS is_neutral_venue,
            COALESCE(m.tournament_type, 'league') AS tournament_type,
            COALESCE(m.tournament_stage, 'regular') AS tournament_stage,
            COALESCE(m.competition_priority, 0) AS competition_priority,
            COALESCE(m.tournament_pressure_score, 0) AS tournament_pressure_score,

            COALESCE(hs.corners, 0) AS home_corners,
            COALESCE(as1.corners, 0) AS away_corners,
            COALESCE(hs.shots_on_target, 0) AS home_sot,
            COALESCE(as1.shots_on_target, 0) AS away_sot,

            f.features_json

        FROM football_feature_snapshots f

        JOIN matches m
            ON m.id = f.match_id

        LEFT JOIN team_match_stats hs
            ON hs.match_id = m.id
           AND hs.is_home = 1

        LEFT JOIN team_match_stats as1
            ON as1.match_id = m.id
           AND as1.is_home = 0

        WHERE
            m.home_goals IS NOT NULL
            AND m.away_goals IS NOT NULL

        ORDER BY
            m.kickoff_date ASC,
            m.id ASC
        """
    )

    rows = pd.read_sql(query, session.bind)

    if rows.empty:
        raise ValueError(
            "No cached football features found. Run: python -m app.cli build-football-features"
        )

    feature_rows = []

    for _, row in rows.iterrows():
        payload = row["features_json"] or {}

        tournament_features = _resolve_tournament_features(
            is_international=row["is_international"],
            is_neutral_venue=row["is_neutral_venue"],
            tournament_type=row["tournament_type"],
            tournament_stage=row["tournament_stage"],
            competition_priority=row["competition_priority"],
            tournament_pressure_score=row["tournament_pressure_score"],
        )

        item = {
            "match_id": row["match_id"],
            "kickoff_date": row["kickoff_date"],
            "league": row["league"],
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "home_goals": row["home_goals"],
            "away_goals": row["away_goals"],
            "has_stats": row["has_stats"],
            "home_corners": row["home_corners"],
            "away_corners": row["away_corners"],
            "home_sot": row["home_sot"],
            "away_sot": row["away_sot"],
            **tournament_features,
        }

        item.update(payload)

        for key, value in tournament_features.items():
            item[key] = _safe_float(value)

        feature_rows.append(item)

    df = pd.DataFrame(feature_rows)
    df["kickoff_date"] = pd.to_datetime(df["kickoff_date"])

    for col in feature_columns():
        if col not in df.columns:
            df[col] = 0.0

    df = _coerce_feature_columns(df)
    df = _add_targets(df)

    return df.fillna(0.0).reset_index(drop=True)


def load_upcoming_frame(
    session: Session,
    limit: int = 30,
) -> pd.DataFrame:
    df = _base_query(session)

    if df.empty:
        return df

    historical_df = df[
        df["home_goals"].notna()
        & df["away_goals"].notna()
    ].copy()

    upcoming_df = df[
        df["home_goals"].isna()
        & df["away_goals"].isna()
        & (
            (df["kickoff_datetime"] >= pd.Timestamp.utcnow().tz_localize(None))
            | (df["kickoff_date"] >= pd.Timestamp.today().normalize())
        )
    ].copy()

    upcoming_df = (
        upcoming_df
        .sort_values(["kickoff_datetime", "kickoff_date", "match_id"])
        .head(limit)
    )

    if upcoming_df.empty:
        return upcoming_df

    upcoming_df = build_upcoming_match_features(
        session=session,
        upcoming_df=upcoming_df,
        historical_df=historical_df,
    )

    upcoming_df = _apply_persistent_elo_for_upcoming(
        session=session,
        df=upcoming_df,
    )

    for col in feature_columns():
        if col not in upcoming_df.columns:
            upcoming_df[col] = 0.0

    upcoming_df = _coerce_feature_columns(upcoming_df)

    return upcoming_df.fillna(0.0).reset_index(drop=True)


def filter_training_frame_for_market(df: pd.DataFrame, market: str) -> pd.DataFrame:
    df = df.copy()

    if market in STATS_REQUIRED_MARKETS:
        if "has_stats" not in df.columns:
            raise ValueError("has_stats column missing for stats market filtering.")

        df = df[df["has_stats"] == True].copy()

    return df.reset_index(drop=True)


def _apply_persistent_elo_for_upcoming(
    session: Session,
    df: pd.DataFrame,
) -> pd.DataFrame:
    if df.empty:
        return df

    ratings_query = text(
        """
        SELECT
            team_id,
            overall_elo,
            attack_elo,
            defense_elo,
            form_elo
        FROM team_ratings
        WHERE sport = 'football'
        """
    )

    ratings_df = pd.read_sql(ratings_query, session.bind)

    if ratings_df.empty:
        return df

    ratings = {
        int(row["team_id"]): row
        for _, row in ratings_df.iterrows()
    }

    df = df.copy()

    for col in [
        "home_elo",
        "away_elo",
        "home_attack_elo",
        "away_attack_elo",
        "home_defense_elo",
        "away_defense_elo",
        "home_elo_form",
        "away_elo_form",
        "elo_diff",
        "elo_form_diff",
        "attack_defense_diff",
    ]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    for i, row in df.iterrows():
        home_team_id = row.get("home_team_id")
        away_team_id = row.get("away_team_id")

        home_rating = ratings.get(int(home_team_id)) if pd.notna(home_team_id) else None
        away_rating = ratings.get(int(away_team_id)) if pd.notna(away_team_id) else None

        if home_rating is not None:
            df.at[i, "home_elo"] = _safe_float(home_rating["overall_elo"])
            df.at[i, "home_attack_elo"] = _safe_float(home_rating["attack_elo"])
            df.at[i, "home_defense_elo"] = _safe_float(home_rating["defense_elo"])
            df.at[i, "home_elo_form"] = _safe_float(home_rating["form_elo"])

        if away_rating is not None:
            df.at[i, "away_elo"] = _safe_float(away_rating["overall_elo"])
            df.at[i, "away_attack_elo"] = _safe_float(away_rating["attack_elo"])
            df.at[i, "away_defense_elo"] = _safe_float(away_rating["defense_elo"])
            df.at[i, "away_elo_form"] = _safe_float(away_rating["form_elo"])

        home_advantage = 0.0 if bool(row.get("is_neutral_venue")) else HOME_ADVANTAGE_ELO

        df.at[i, "elo_diff"] = (
            _safe_float(df.at[i, "home_elo"])
            + home_advantage
            - _safe_float(df.at[i, "away_elo"])
        )

        df.at[i, "elo_form_diff"] = (
            _safe_float(df.at[i, "home_elo_form"])
            - _safe_float(df.at[i, "away_elo_form"])
        )

        df.at[i, "attack_defense_diff"] = (
            _safe_float(df.at[i, "home_attack_elo"])
            - _safe_float(df.at[i, "away_defense_elo"])
        )

    return df.fillna(0.0)


def _base_query(session: Session) -> pd.DataFrame:
    query = text(
        """
        SELECT
            m.id AS match_id,
            m.kickoff_date,
            m.kickoff_datetime,
            m.league,
            m.home_team,
            m.away_team,
            m.home_team_id,
            m.away_team_id,
            m.home_goals,
            m.away_goals,
            m.has_stats,
            m.has_odds,
            m.odds_unavailable,

            COALESCE(m.is_international, false) AS is_international,
            COALESCE(m.is_neutral_venue, false) AS is_neutral_venue,
            COALESCE(m.tournament_type, 'league') AS tournament_type,
            COALESCE(m.tournament_stage, 'regular') AS tournament_stage,
            COALESCE(m.competition_priority, 0) AS competition_priority,
            COALESCE(m.tournament_pressure_score, 0) AS tournament_pressure_score,

            COALESCE(hs.shots_on_target, 0) AS home_sot,
            COALESCE(hs.corners, 0) AS home_corners,
            COALESCE(hs.possession, 0) AS home_possession,
            COALESCE(hs.fouls, 0) AS home_fouls,
            COALESCE(hs.cards, 0) AS home_cards,
            COALESCE(hs.keeper_saves, 0) AS home_keeper_saves,

            COALESCE(as1.shots_on_target, 0) AS away_sot,
            COALESCE(as1.corners, 0) AS away_corners,
            COALESCE(as1.possession, 0) AS away_possession,
            COALESCE(as1.fouls, 0) AS away_fouls,
            COALESCE(as1.cards, 0) AS away_cards,
            COALESCE(as1.keeper_saves, 0) AS away_keeper_saves

        FROM matches m

        LEFT JOIN team_match_stats hs
            ON hs.match_id = m.id
           AND hs.is_home = 1

        LEFT JOIN team_match_stats as1
            ON as1.match_id = m.id
           AND as1.is_home = 0

        WHERE (
            (
                m.home_goals IS NULL
                AND m.away_goals IS NULL
                AND (
                    m.kickoff_datetime >= NOW()
                    OR m.kickoff_date >= CURRENT_DATE
                )
            )

            OR

            (
                m.home_goals IS NOT NULL
                AND m.away_goals IS NOT NULL
            )
        )

        ORDER BY
            COALESCE(m.kickoff_datetime, m.kickoff_date) ASC,
            m.id ASC
        """
    )

    df = pd.read_sql(query, session.bind)

    if df.empty:
        return df

    if "kickoff_datetime" in df.columns:
        df["kickoff_datetime"] = pd.to_datetime(
            df["kickoff_datetime"],
            errors="coerce",
        )

    df["kickoff_date"] = pd.to_datetime(
        df["kickoff_date"],
        errors="coerce",
    )

    for col in feature_columns():
        if col not in df.columns:
            df[col] = 0.0

    df = _coerce_feature_columns(df)

    for index, row in df.iterrows():
        tournament_features = _resolve_tournament_features(
            is_international=row.get("is_international"),
            is_neutral_venue=row.get("is_neutral_venue"),
            tournament_type=row.get("tournament_type"),
            tournament_stage=row.get("tournament_stage"),
            competition_priority=row.get("competition_priority"),
            tournament_pressure_score=row.get("tournament_pressure_score"),
        )

        _assign_numeric_features(df, index, tournament_features)

    return df.reset_index(drop=True)


def _add_targets(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in [
        "home_goals",
        "away_goals",
        "home_corners",
        "away_corners",
        "home_sot",
        "away_sot",
    ]:
        if col not in df.columns:
            df[col] = 0

        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    total_goals = df["home_goals"] + df["away_goals"]
    total_corners = df["home_corners"] + df["away_corners"]
    total_sot = df["home_sot"] + df["away_sot"]

    df["target_home_win"] = (df["home_goals"] > df["away_goals"]).astype(int)
    df["target_away_win"] = (df["away_goals"] > df["home_goals"]).astype(int)
    df["target_draw"] = (df["home_goals"] == df["away_goals"]).astype(int)

    df["target_double_chance_1x"] = (df["home_goals"] >= df["away_goals"]).astype(int)
    df["target_double_chance_x2"] = (df["away_goals"] >= df["home_goals"]).astype(int)
    df["target_double_chance_12"] = (df["home_goals"] != df["away_goals"]).astype(int)

    df["target_over_1_5"] = (total_goals > 1.5).astype(int)
    df["target_under_1_5"] = (total_goals <= 1.5).astype(int)
    df["target_over_2_5"] = (total_goals > 2.5).astype(int)
    df["target_under_2_5"] = (total_goals <= 2.5).astype(int)
    df["target_over_3_5"] = (total_goals > 3.5).astype(int)
    df["target_under_3_5"] = (total_goals <= 3.5).astype(int)

    df["target_btts_yes"] = ((df["home_goals"] > 0) & (df["away_goals"] > 0)).astype(int)
    df["target_btts_no"] = ((df["home_goals"] == 0) | (df["away_goals"] == 0)).astype(int)

    df["target_home_over_0_5"] = (df["home_goals"] > 0).astype(int)
    df["target_away_over_0_5"] = (df["away_goals"] > 0).astype(int)

    df["target_home_clean_sheet"] = (df["away_goals"] == 0).astype(int)
    df["target_away_clean_sheet"] = (df["home_goals"] == 0).astype(int)

    df["target_corners_over_8_5"] = (total_corners > 8.5).astype(int)
    df["target_sot_over_8_5"] = (total_sot > 8.5).astype(int)

    df["target_draw_no_bet_home"] = (df["home_goals"] > df["away_goals"]).astype(int)
    df["target_draw_no_bet_away"] = (df["away_goals"] > df["home_goals"]).astype(int)

    df["target_home_win_to_nil"] = (
        (df["home_goals"] > df["away_goals"])
        & (df["away_goals"] == 0)
    ).astype(int)

    df["target_away_win_to_nil"] = (
        (df["away_goals"] > df["home_goals"])
        & (df["home_goals"] == 0)
    ).astype(int)

    goal_diff = df["home_goals"] - df["away_goals"]
    away_goal_diff = df["away_goals"] - df["home_goals"]

    df["target_ah_home_plus_0_5"] = ((goal_diff + 0.5) > 0).astype(int)
    df["target_ah_away_plus_0_5"] = ((away_goal_diff + 0.5) > 0).astype(int)
    df["target_ah_home_minus_0_5"] = ((goal_diff - 0.5) > 0).astype(int)
    df["target_ah_away_minus_0_5"] = ((away_goal_diff - 0.5) > 0).astype(int)

    df["target_ah_home_plus_1_5"] = ((goal_diff + 1.5) > 0).astype(int)
    df["target_ah_away_plus_1_5"] = ((away_goal_diff + 1.5) > 0).astype(int)
    df["target_ah_home_minus_1_5"] = ((goal_diff - 1.5) > 0).astype(int)
    df["target_ah_away_minus_1_5"] = ((away_goal_diff - 1.5) > 0).astype(int)

    df["target_home_away_home"] = (
        df["home_goals"] > df["away_goals"]
    ).astype(int)

    df["target_home_away_away"] = (
        df["away_goals"] > df["home_goals"]
    ).astype(int)

    adjusted_plus = goal_diff + 1.0
    adjusted_minus = goal_diff - 1.0

    df["target_handicap_result_home_plus_1_0"] = (
        adjusted_plus > 0
    ).astype(int)

    df["target_handicap_result_draw_plus_1_0"] = (
        adjusted_plus == 0
    ).astype(int)

    df["target_handicap_result_away_plus_1_0"] = (
        adjusted_plus < 0
    ).astype(int)

    df["target_handicap_result_home_minus_1_0"] = (
        adjusted_minus > 0
    ).astype(int)

    df["target_handicap_result_draw_minus_1_0"] = (
        adjusted_minus == 0
    ).astype(int)

    df["target_handicap_result_away_minus_1_0"] = (
        adjusted_minus < 0
    ).astype(int)

    df["target_result_total_home_over_1_5"] = (
        (df["home_goals"] > df["away_goals"])
        & (total_goals > 1.5)
    ).astype(int)

    df["target_result_total_home_over_2_5"] = (
        (df["home_goals"] > df["away_goals"])
        & (total_goals > 2.5)
    ).astype(int)

    df["target_result_total_home_over_3_5"] = (
        (df["home_goals"] > df["away_goals"])
        & (total_goals > 3.5)
    ).astype(int)

    df["target_result_total_draw_over_1_5"] = (
        (df["home_goals"] == df["away_goals"])
        & (total_goals > 1.5)
    ).astype(int)

    df["target_result_total_draw_over_2_5"] = (
        (df["home_goals"] == df["away_goals"])
        & (total_goals > 2.5)
    ).astype(int)

    df["target_result_total_draw_over_3_5"] = (
        (df["home_goals"] == df["away_goals"])
        & (total_goals > 3.5)
    ).astype(int)

    df["target_result_total_away_over_1_5"] = (
        (df["away_goals"] > df["home_goals"])
        & (total_goals > 1.5)
    ).astype(int)

    df["target_result_total_away_over_2_5"] = (
        (df["away_goals"] > df["home_goals"])
        & (total_goals > 2.5)
    ).astype(int)

    df["target_result_total_away_over_3_5"] = (
        (df["away_goals"] > df["home_goals"])
        & (total_goals > 3.5)
    ).astype(int)

    return df


def _add_advanced_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.sort_values(["kickoff_date", "match_id"]).reset_index(drop=True)

    for col in feature_columns():
        if col not in df.columns:
            df[col] = 0.0

    df = _coerce_feature_columns(df)

    elo: dict[str, float] = {}
    attack_elo: dict[str, float] = {}
    defense_elo: dict[str, float] = {}
    elo_history: dict[str, list[float]] = {}

    for i, row in df.iterrows():
        home = row["home_team"]
        away = row["away_team"]
        date = row["kickoff_date"]

        tournament_features = _resolve_tournament_features(
            is_international=row.get("is_international"),
            is_neutral_venue=row.get("is_neutral_venue"),
            tournament_type=row.get("tournament_type"),
            tournament_stage=row.get("tournament_stage"),
            competition_priority=row.get("competition_priority"),
            tournament_pressure_score=row.get("tournament_pressure_score"),
        )

        _assign_numeric_features(df, i, tournament_features)

        league_hist = _league_history(df, row["league"], date)
        league_profile = _league_profile(league_hist)
        _assign_numeric_features(df, i, league_profile)

        home_elo = elo.get(home, INITIAL_ELO)
        away_elo = elo.get(away, INITIAL_ELO)

        home_attack = attack_elo.get(home, INITIAL_ELO)
        away_attack = attack_elo.get(away, INITIAL_ELO)

        home_defense = defense_elo.get(home, INITIAL_ELO)
        away_defense = defense_elo.get(away, INITIAL_ELO)

        home_elo_form = _elo_form(elo_history.get(home, []), home_elo)
        away_elo_form = _elo_form(elo_history.get(away, []), away_elo)

        home_advantage = 0.0 if bool(tournament_features["is_neutral_venue"]) else HOME_ADVANTAGE_ELO

        df.at[i, "home_elo"] = home_elo
        df.at[i, "away_elo"] = away_elo
        df.at[i, "elo_diff"] = (home_elo + home_advantage) - away_elo

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
        _assign_numeric_features(df, i, _h2h_features(h2h, home, away))

        home_home_hist = df[(df["home_team"] == home) & (df["kickoff_date"] < date)].tail(8)
        away_away_hist = df[(df["away_team"] == away) & (df["kickoff_date"] < date)].tail(8)

        df.at[i, "home_home_win_rate"] = _home_win_rate(home_home_hist, home)
        df.at[i, "away_away_win_rate"] = _away_win_rate(away_away_hist, away)
        df.at[i, "home_current_streak"] = _current_streak(home_hist, home)
        df.at[i, "away_current_streak"] = _current_streak(away_hist, away)

        for key, value in _team_profile(home_hist, home).items():
            _assign_numeric_features(df, i, {f"home_{key}": value})

        for key, value in _team_profile(away_hist, away).items():
            _assign_numeric_features(df, i, {f"away_{key}": value})

        home_strength = _team_strength(home_hist, home)
        away_strength = _team_strength(away_hist, away)

        df.at[i, "team_strength_diff"] = home_strength - away_strength

        if pd.notna(row["home_goals"]) and pd.notna(row["away_goals"]):
            new_home_elo, new_away_elo = _update_result_elo(
                home_elo=home_elo,
                away_elo=away_elo,
                home_goals=float(row["home_goals"]),
                away_goals=float(row["away_goals"]),
                home_advantage=home_advantage,
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


def _resolve_tournament_features(
    *,
    is_international,
    is_neutral_venue,
    tournament_type,
    tournament_stage,
    competition_priority,
    tournament_pressure_score,
) -> dict[str, float]:
    stage = str(tournament_stage or "regular").lower().strip()
    tournament = str(tournament_type or "league").lower().strip()

    is_qualifier = stage == "qualifier" or tournament == "international_qualifier"
    is_friendly = stage == "friendly" or tournament == "international_friendly"

    return {
        "is_international": float(bool(is_international)),
        "is_neutral_venue": float(bool(is_neutral_venue)),
        "is_knockout": float(stage in TOURNAMENT_KNOCKOUT_STAGES),
        "is_final": float(stage == "final"),
        "is_semifinal": float(stage == "semifinal"),
        "is_qualifier": float(is_qualifier),
        "is_friendly": float(is_friendly),
        "competition_priority": _safe_float(competition_priority),
        "tournament_pressure_score": _safe_float(tournament_pressure_score),
    }


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
    home_advantage: float = HOME_ADVANTAGE_ELO,
) -> tuple[float, float]:
    adjusted_home = home_elo + home_advantage

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

    return attack_rating + movement, defense_rating - movement


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


def _league_history(df: pd.DataFrame, league: str, date) -> pd.DataFrame:
    return df[
        (df["league"] == league)
        & (df["kickoff_date"] < date)
        & df["home_goals"].notna()
        & df["away_goals"].notna()
    ]


def build_upcoming_match_features(
    session: Session,
    upcoming_df: pd.DataFrame,
    historical_df: pd.DataFrame,
) -> pd.DataFrame:
    upcoming_df = upcoming_df.copy()
    historical_df = historical_df.sort_values(["kickoff_date", "match_id"])

    for col in feature_columns():
        if col not in upcoming_df.columns:
            upcoming_df[col] = 0.0

    upcoming_df = _coerce_feature_columns(upcoming_df)

    for i, row in upcoming_df.iterrows():
        home = row["home_team"]
        away = row["away_team"]
        league = row["league"]

        tournament_features = _resolve_tournament_features(
            is_international=row.get("is_international"),
            is_neutral_venue=row.get("is_neutral_venue"),
            tournament_type=row.get("tournament_type"),
            tournament_stage=row.get("tournament_stage"),
            competition_priority=row.get("competition_priority"),
            tournament_pressure_score=row.get("tournament_pressure_score"),
        )

        _assign_numeric_features(upcoming_df, i, tournament_features)

        home_hist = historical_df[
            (historical_df["home_team"] == home)
            | (historical_df["away_team"] == home)
        ].tail(8)

        away_hist = historical_df[
            (historical_df["home_team"] == away)
            | (historical_df["away_team"] == away)
        ].tail(8)

        league_hist = historical_df[
            historical_df["league"] == league
        ].tail(200)

        h2h_hist = historical_df[
            (
                (historical_df["home_team"] == home)
                & (historical_df["away_team"] == away)
            )
            |
            (
                (historical_df["home_team"] == away)
                & (historical_df["away_team"] == home)
            )
        ].tail(6)

        upcoming_df.at[i, "home_win_rate"] = _win_rate(home_hist, home)
        upcoming_df.at[i, "away_win_rate"] = _win_rate(away_hist, away)

        upcoming_df.at[i, "home_goal_diff"] = _goal_diff(home_hist, home)
        upcoming_df.at[i, "away_goal_diff"] = _goal_diff(away_hist, away)

        upcoming_df.at[i, "home_form_score"] = _form_score(home_hist, home)
        upcoming_df.at[i, "away_form_score"] = _form_score(away_hist, away)

        _assign_numeric_features(upcoming_df, i, _h2h_features(h2h_hist, home, away))
        _assign_numeric_features(upcoming_df, i, _league_profile(league_hist))

        for key, value in _team_profile(home_hist, home).items():
            _assign_numeric_features(upcoming_df, i, {f"home_{key}": value})

        for key, value in _team_profile(away_hist, away).items():
            _assign_numeric_features(upcoming_df, i, {f"away_{key}": value})

        upcoming_df.at[i, "team_strength_diff"] = (
            _team_strength(home_hist, home)
            - _team_strength(away_hist, away)
        )

    return upcoming_df.fillna(0.0)


def _league_profile(hist: pd.DataFrame) -> dict[str, float]:
    if hist.empty:
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

    games = len(hist)

    home_wins = (hist["home_goals"] > hist["away_goals"]).sum()
    away_wins = (hist["away_goals"] > hist["home_goals"]).sum()
    draws = (hist["home_goals"] == hist["away_goals"]).sum()

    total_goals = hist["home_goals"] + hist["away_goals"]
    total_corners = hist["home_corners"] + hist["away_corners"]
    total_sot = hist["home_sot"] + hist["away_sot"]

    btts = ((hist["home_goals"] > 0) & (hist["away_goals"] > 0)).sum()
    over_2_5 = (total_goals > 2.5).sum()

    return {
        "league_home_win_rate": float(home_wins / games),
        "league_away_win_rate": float(away_wins / games),
        "league_draw_rate": float(draws / games),
        "league_avg_goals": float(total_goals.mean()),
        "league_btts_rate": float(btts / games),
        "league_over_2_5_rate": float(over_2_5 / games),
        "league_avg_corners": float(total_corners.mean()),
        "league_avg_sot": float(total_sot.mean()),
    }


def _assign_numeric_features(
    df: pd.DataFrame,
    index,
    values: dict[str, float],
) -> None:
    for key, value in values.items():
        if key not in df.columns:
            df[key] = 0.0

        if str(df[key].dtype) == "bool":
            df[key] = df[key].astype(float)

        if not pd.api.types.is_numeric_dtype(df[key]):
            df[key] = pd.to_numeric(df[key], errors="coerce").fillna(0.0).astype(float)

        df.at[index, key] = _safe_float(value)


def _coerce_feature_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in feature_columns():
        if col not in df.columns:
            df[col] = 0.0

        if str(df[col].dtype) == "bool":
            df[col] = df[col].astype(float)
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    return df


def _safe_float(value) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0